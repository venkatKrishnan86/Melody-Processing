#! /usr/bin/python
import numpy as np
import os,sys, copy
import matplotlib.pyplot as plt
import math
import scipy.ndimage.filters as filters
#import pls

import pitchHistogram as PH

eps = np.finfo(np.float).eps

def groupIndices(indexes):
    """
    This function groups indexes. This is often needed to produce segments given indices.
    """
    segments = []
    segStart = indexes[0]
    N = len(indexes)
    for ii in range(len(indexes)):
        if ii == N-1:
            segments.append([segStart, indexes[ii]])
            return np.array(segments)
        if indexes[ii]+1 != indexes[ii+1]:
            segments.append([segStart, indexes[ii]])
            segStart = indexes[ii+1]

    return np.array(segments)




def ComputeLocalVariance(pCents, phop, windowLen):
    var_len = float(windowLen)/1000.0    #in ms
    var_samples = int(round(var_len/phop))
    
    pVar = np.finfo(np.float).max*np.ones(pCents.shape[0])
    for i in range(0+var_samples,pCents.shape[0]-var_samples):
        pVar[i] = min(np.var(pCents[i:i+var_samples]),np.var(pCents[i-var_samples:i]))

    return pVar

class nyasSegmentation():
    
    swarCents = []
    
    def __init__(self):
        print "Initialization PitchProcessing..."
        
    
    def ComputeNyasCandidates(self, pitch, tonic, phop, vicinityThsld = 30, timeAwayThsld = 100, varianceWinLen = 100, varianceThsld = 30):
        """
        This function computed the nyas candidates, essentially flat swar regions for each swara separately.
        Params:
            vicinityThsld (cents): absolute deviation (difference) around the mean swara location which is considered as within the vicinity of the swara
            timeAwayThsld (ms): The maximum duration which is allowed for the melody to be in the close vicinity of neighboring swar before we declare that melody has moved to another swar.
            varianceThsld (cents): threshold on the variance of the pitch contour in cents used for estimating regions corresponding to stable melody.  
            varianceWinLen (ms): window length for computing variance for estimating stable melodic regions
        """
        phObj = PH.PitchHistogram(pitch, tonic)
        ### everytime this function is called just reset the old NyasInfo variable
        self.nyasInfo={}
        #getting valid swar locations (within one octave)
        phObj.ValidSwarLocEstimation(Oct_fold=1)
        #converting swar locations in indexes to cents
        phObj.SwarLoc2Cents()
        #since the swar locations are computed using octave folded histogram, propagating them to other octaves
        phObj.ExtendSwarOctaves()
        self.swarCents = phObj.swarCents
        self.pCents = phObj.pCents
        self.phop = phop
        ### Algorithm 4: This algorith is improved version of Algo2. There are two main imrpovements
        # 1) Different broad thresholds for terminating nyas depending upon neighbouring scale degrees. Bigger the diff bigger threshold. 
        # 2) Criterion for nyas termination when pitch doesn't cross broad threshold but reaches another note. Previously a condition was set on the time that pitch spends close to the neighbouring notes. the problem is that sometimes due to the smooth transitions the pitch is not very close (< narrow trshold) to the neighbouring note. But we know that its not an ornamentation but a different note becasue the pitch remain flat for sometime. in case of ornamentation its hardly flat. So lets put the minimum time criterion on both <narrow threshold of neighbour and flat region. Where the flat region determination is based on local variance calcualted using function XXX
        
        #improvements
        #1) Identify points of potential segmentation based on nice musical logic and then within each detected flat segment shrink the segment to contain the valid segmentation points. THis will improve the performance where there is a glide taken with a kan kind of shape. in current implementatino we kind of cut it in the middle
        #2) Improve oerlap removal code. Currently it just removes the short segment, but in reality we would liketo have that segment in a non overlapping way. Better would be to choose at each instance from a segment which is highest length.

        #two level of threshold
        narrow_tshld = vicinityThsld
        nghbr_thshld = float(timeAwayThsld)/1000    # time in ms which is the max time allowed for a pitch deviation to be close to a nieghbouring note
        var_threshold = float(varianceThsld)    # in cents
        swar_neighbour=-1
        neighbour_cnt = 0
        nghbr_thshld_samples = (nghbr_thshld/self.phop)
        #computing local variance for identifying note changes when diff doesn't reach broad threshold
        self.pVar = ComputeLocalVariance(self.pCents, self.phop, varianceWinLen)
        ind_flat = np.where(self.pVar<var_threshold)[0]
        flat_notes = 0*self.pCents
        flat_notes[ind_flat]=1
        #iterating over all the swar locations
        for i, swar in enumerate(self.swarCents):
            if ((i<=0)|(i>=len(self.swarCents)-1)):
                broad_tshld_hi= 150.0
                broad_tshld_lo= 150.0
            else:
                broad_tshld_hi = (self.swarCents[i+1]-self.swarCents[i])+50
                broad_tshld_lo = (self.swarCents[i]-self.swarCents[i-1])+50
                print swar, broad_tshld_hi, broad_tshld_lo
            # just to make process 249784fast lets find in one shot all the points which are atleast closer than narrow threshold
            ind_narrow = np.where((self.pCents<swar+narrow_tshld)&(self.pCents>swar-narrow_tshld))[0]
            self.nyasInfo[swar]=[]
            pointer1=0     # index of ind_narrow, which becomes the onset location
            while True:
                if (len(ind_narrow)<=0):
                    break
                first_tick = ind_narrow[pointer1]    # first tick stores the onset location
                second_tick = -1            # this is supposed to store the offset location
                pointer2 = first_tick            # this pointer is incremental pointer for note (during the note)
                neighbour_cnt = 0            # this counter measures the samples of pitch close to the neighbouring swar (needed for improving algo2 over algo1)
                overallOutCnt = 0            # this counter measures the samples when the pointer is outside the close vicinity of a note. This shouldn't be too high
                while True:
                    if(neighbour_cnt>nghbr_thshld_samples) | (overallOutCnt>2*nghbr_thshld_samples):
                        self.nyasInfo[swar].append([first_tick, second_tick])
                        break
                    if(abs(self.pCents[pointer2]-swar)<narrow_tshld):    #if <narrow just make sure second_tick is -1 (benefit when swar is fluctuating and it comes back within narrow threshold)
                        if(second_tick!=-1):
                            second_tick=-1
                            neighbour_cnt=0
                            overallOutCnt=0
                    else:
                        overallOutCnt = overallOutCnt+1
                        if(second_tick==-1):    # if swar is not with narrow thsld, mark this location (for the first time) so that we have it as the note offset later
                            second_tick = pointer2 -1
                            # at this point start measuring how much time the pitch remains close (very close <narrow) to neighboring notes. And if this crosses threshold we can terminate this note. This is done to accomodate big deviations which are a part of nyas but they are differentiated because they dont remain close to neighboring notes for a long time_pitch
                            #determine whether the deviation is towards hi pitch or low pitch direction with respect to swar frequency
                            if ((self.pCents[pointer2]-swar)>0):
                                if(i+1>=len(self.swarCents)):
                                    swar_neighbour = swar    # just assigning dummy same swar, because this is a extreme case happen because at silence the pitch goes really really high. So for the last swar this will create out of bound problems
                                else:                        
                                    swar_neighbour = self.swarCents[i+1]
                            else:
                                if(i-1<0):
                                    swar_neighbour = swar    # Similar logic for dummy condition as before
                                else:                        
                                    swar_neighbour = self.swarCents[i-1]
                        else:
                            if((abs(self.pCents[pointer2]-swar_neighbour)<narrow_tshld)|(flat_notes[pointer2]==1)):
                                neighbour_cnt=neighbour_cnt+1
                    #if(abs(self.pCents[pointer2]-swar)>broad_tshld):    # if the difference becomes > broad threshold, terminate this note
                    if(((self.pCents[pointer2]-swar)>broad_tshld_hi)|((swar-self.pCents[pointer2])>broad_tshld_lo)):    # if the difference becomes > broad threshold, terminate this note
                        self.nyasInfo[swar].append([first_tick, second_tick])
                        break
                    elif pointer2>=len(self.pCents)-1:    #also if pointer2 reaches end of pitch file terminate the note
                        self.nyasInfo[swar].append([first_tick, pointer2])
                        break
                    pointer2 = pointer2+1
                new_indexes = np.where(ind_narrow>second_tick)[0]        # find the next location to start the onset
                if((pointer2>=(len(self.pCents)-1))|(len(new_indexes)==0)):
                    break
                pointer1=new_indexes[0]

    def FilterNyasCandidates(self, min_nyas_duration=150.0):
        
        ### Thresholds for filtering out weak nyas candidates
        min_nyas_dur = min_nyas_duration/1000 # in ms
        small_allowed_gap = 100.0/1000    #in ms

        
        #derived thresholds
        min_nyas_samples = (float(min_nyas_dur)/self.phop)
        small_allowed_gap_samples = (float(small_allowed_gap)/self.phop)

        
        ### PRE MACHINE LEARNING FILTERING BASED ON INTUITIVE THRESHOLDS (MILD OBVIOUS FILTERING)
        ### NOTE: THIS ORDER OF FILTERING is VERY IMP. THE ORDER SHOULD NOT BE CHANGED!!!!!!!!!!!!!!!!!!

        ### [FIRST filtering] Filter out nyas candidates which are less than certain duration
        for swar in self.swarCents:
            del_ind = []
            for i, pair in enumerate(self.nyasInfo[swar]):
                if((pair[1]-pair[0])<min_nyas_samples):
                    del_ind.append(i)
            
            for ind in reversed(del_ind):
                self.nyasInfo[swar].pop(ind)

        ### [Second] Bridging the gap between two nyas candidates if they are very very close, This might happen because of small octave error or some pitch error.
        for swar in self.swarCents:
            del_ind = []
            for i, pair in enumerate(self.nyasInfo[swar][:-1]):
                if((self.nyasInfo[swar][i+1][0]-self.nyasInfo[swar][i][1])<small_allowed_gap_samples):
                    print "yes" + str(self.nyasInfo[swar][i])
                    self.nyasInfo[swar][i][1]=self.nyasInfo[swar][i+1][1]
                    del_ind.append(i+1)
                
            
            for ind in reversed(del_ind):
                self.nyasInfo[swar].pop(ind)
        
        ### [Second] Joining two same nyas swar if they are close. This step is little different than previous step. Previous step handled any short (very short) gap between two nyas usually because of some pitch related errors. This joining algorithm handles ornamentations with big deviations >broad threshold. This big deviations are very hard to handle while generating nyas candidates because we have performed causal processing. Now that we know all the cnadidates we can join them based on some characteristics of the gap (which represent an ornamentation and not a note). This way we make system little non causal and can get better results.     NOTE that if you are planning to do this, make sure you dont loose many nyas because of minimum duration which might be combined. So keep the minimum duration threshold for filtering quite low and let machine learning does the magic.


    def GetNyasSwarInfo(self):
        return self.nyasInfo

        
    def DumpNyasInfo(self, filename = 'default.textgrid'):
        """
        This function generates a text grid file in which all the nyas swars are marked. This file can be used to semiautomated annotations. Since there can be overlapping nyas candidates, because in some situations both of them are valid candidates, we need two tires to handle it.
        """
        
        #dumping data in a format which depends upon the extension of the file name specified
        file, fileext = os.path.splitext(filename)
        
        # There is an obvious reason that only two tires of textgrid are enough to dump the nyas candidates, since there can only be two overlapping nyas candiadtes (considering we dont do octave folded pitch difference, which we won't)
        
        # creating an array of strings for annotations
        swarNames = ["S", "r", "R", "g", "G","m","M","P","d","D","n","N"]
        
        pitch_zero_vals = -5000
        # to check the overlap of the swars creating an occupied indicator array
        nyas_fill1 = (0*self.pCents)+pitch_zero_vals
        nyas_fill2 = (0*self.pCents)+pitch_zero_vals
        nyas_fill_info1 = [0]*(self.pCents.shape[0])
        nyas_fill_info2 = [0]*(self.pCents.shape[0])
        
        n_nyas1 =0
        n_nyas2 =0
        
        #filling information
        for swar in self.swarCents:
            for pair in self.nyasInfo[swar]:
                if(sum(nyas_fill1[pair[0]:pair[1]+1])==(pair[1]+1-pair[0])*pitch_zero_vals):
                    nyas_fill1[pair[0]:pair[1]+1]=swar
                    nyas_fill_info1[pair[0]]={'swar':swarNames[int(round(swar/100.0)%12)],'dur':pair}
                    n_nyas1 = n_nyas1 +1
                elif (sum(nyas_fill2[pair[0]:pair[1]+1])==(pair[1]+1-pair[0])*pitch_zero_vals):
                    nyas_fill2[pair[0]:pair[1]+1]=swar
                    nyas_fill_info2[pair[0]]={'swar':swarNames[int(round(swar/100.0)%12)],'dur':pair}
                    n_nyas2 = n_nyas2 + 1
                else:
                    print "What the f is happening here!! at " + str(swar) + " " + str(pair[0])
        print n_nyas1, n_nyas2
        
        #Combining information
        nyas_fill = [nyas_fill1, nyas_fill2]
        nyas_fill_info = [nyas_fill_info1, nyas_fill_info2]
        n_nyas = [n_nyas1, n_nyas2]
        
        
        N_tiers = 2;
        tierNames = ["First", "Second"]
        end_time = (self.pCents.shape[0])*self.phop
        
        if(fileext==".textgrid"):
            fid = open(filename,'wt')    # open this file here only if its a textgrid file        
            #writing header
            fid.write('File type = "ooTextFile"' + '\n')
            fid.write('Object class = "TextGrid"' + '\n')
            fid.write('\n')
            fid.write('xmin = 0' + '\n')
            fid.write('xmax = ' +str(end_time) + '\n')
            fid.write('tiers? <exists>' + '\n')
            fid.write('size = ' + str(N_tiers) + '\n')
            fid.write('item []:' + '\n')
        
        for tier in range(0,N_tiers):
            
            #if its a sonic visualizer file, we have to create two files for each tier.
            if(fileext==".lib"):
                fid = open(file+"_tier_"+str(tier+1)+fileext,'wt')
            
            changepoints = np.where(np.array(nyas_fill[tier][1:]-nyas_fill[tier][:-1])!=0)[0]+1
            changepoints = np.append(0,changepoints)
            changepoints = np.append(changepoints, len(nyas_fill[tier]))
            
            if(fileext==".textgrid"):
                tier_ind = tier+1
                fid.write('    item [%d]: \n'%tier_ind)
                fid.write('        class = "IntervalTier" \n')
                fid.write('        name = "%s" \n'%tierNames[tier])
                fid.write('        xmin = 0 \n')
                fid.write('        xmax = %f \n'%end_time)
                n_nyas_tier = changepoints.shape[0]-1
                fid.write('        intervals: size = %d\n'%n_nyas_tier)
            

                cnt2=1
                for i,point in enumerate(changepoints[:-1]):
                    if nyas_fill_info[tier][point]==0:
                        xmin = point*(self.phop)
                        xmax = changepoints[i+1]*(self.phop)
                        fid.write('        intervals [%d]: \n'%cnt2)
                        fid.write('            xmin = %f \n'%xmin)
                        fid.write('            xmax = %f \n'%xmax)
                        fid.write('            text = "%s" \n'%"")
                        cnt2+=1
                    else:
                        xmin = point*(self.phop)
                        xmax = changepoints[i+1]*(self.phop)                    
                        fid.write('        intervals [%d]: \n'%cnt2)
                        fid.write('            xmin = %f \n'%xmin)
                        fid.write('            xmax = %f \n'%xmax)
                        fid.write('            text = "%s" \n'%nyas_fill_info[tier][point]['swar'])
                        cnt2+=1    
            elif (fileext==".lib"):
                
                for i,point in enumerate(changepoints[:-1]):
                    if nyas_fill_info[tier][point]==0:
                        xmin = point*(self.phop)
                        xmax = changepoints[i+1]*(self.phop)
                        fid.write('%f\t%f\t"%s"\n'%(xmin,xmax,"-"))
                    else:
                        xmin = point*(self.phop)
                        xmax = changepoints[i+1]*(self.phop)                    
                        fid.write('%f\t%f\t"%s"\n'%(xmin,xmax,nyas_fill_info[tier][point]['swar']))

    
    def segmentPitch(self, pitch, tonic, phop):

        self.ComputeNyasCandidates(pitch, tonic, phop)
        self.FilterNyasCandidates()

        segmentationOutput = []

        for key in self.nyasInfo.keys():
            for segment in self.nyasInfo[key]:
                segmentationOutput.append(segment)

        #Note that these segments are the flat regions only. We need to generate all segments. But to do that we have to make sure there is no overlapping segments
        flatSegments = self.removeSegmentsThatOverlap(segmentationOutput)

        #
        arr = np.zeros(self.pCents.shape[0])
        arr[0]=1
        arr[-1]=1
        for segment in flatSegments:
            arr[segment[0]]=1
            arr[segment[1]]=1

        ind_nz = np.where(arr==1)[0]
        allSegments=[]
        for i, k in enumerate(ind_nz[:-1]):
            allSegments.append([ind_nz[i], ind_nz[i+1]])

        allSegments = np.array(allSegments)*self.phop

        ind_sort = np.argsort(allSegments[:,0],axis=0)   #sorting only the starting of the segments #NOTE that there might be overlapping segments from this method

        allSegments = allSegments[ind_sort]

        return  allSegments, np.array(flatSegments)*self.phop

    def removeSegmentsThatOverlap(self, segmentationOutput):
        popList=[]
        for i,seg1 in enumerate(segmentationOutput):
            for j,seg2 in enumerate(segmentationOutput):
                if i==j:
                    continue
                if ((seg1[0]-seg2[0]<0 and seg1[1]-seg2[0]>0)|(seg2[0]-seg1[1]<0 and seg2[1]-seg1[1] >0)):
                    if seg1[1]-seg1[0] >seg2[1]-seg2[0]:
                        popList.append(j)
                    else:
                        popList.append(i)
        popList = list(set(popList))
        popList = np.sort(np.array(popList)).tolist()
        for i in reversed(popList):
            segmentationOutput.pop(i)

        return segmentationOutput
        
    def ReadNyasAnnotationsPerTag(self, annotation_file):
        """
        This function returns segments (only the ones which were detected as nyas candidates) along with the tags (ground truth) whether they are nyas or non-nyas or combine part
        NOTE: that this output will not have trivial segments of pitch which are zero valued, because they were removed from nyas candidate estimation already
        """
        tg_dict={}
        tg_dict['nyas']=[]
        tg_dict['non-nyas']=[]
        tg_dict['combine']=[]

        par_obj = tgp.TextGrid.load(annotation_file)	#loading the object
        tiers= tgp.TextGrid._find_tiers(par_obj)	#finding existing tiers

        for tier in tiers:

            tier_details = tier.make_simple_transcript()

            for line in tier_details:

                if line[2]=='c':
                    tg_dict['combine'].append([float(line[0]), float(line[1]),line[2]])
                elif line[2].find('-y')!=-1:
                    tg_dict['nyas'].append([float(line[0]), float(line[1]),line[2].split('-')[0]])
                elif len(line[2]) ==1:
                    tg_dict['non-nyas'].append([float(line[0]), float(line[1]),line[2]])
                elif len(line[2])!=0:
                    print "we have got problem in ", line

        self.NyasAnnotations = tg_dict

        return True

    def ReadNyasAnnotations(self, annotation_file):
        """
        This function returns all the segments (nyas candidates + the segments between them) along with tags(ground truth)
        As some of these segments might contain trivial segments like silence regions we need to remove these trivial cases explicity.
        So if you are using this function for classification task where you need to classify all the segments, perform this trivial segment removal step after this function.
        """
        tg_dict={}
        tg_dict['nyas']=[]
        tg_dict['non-nyas']=[]

        par_obj = tgp.TextGrid.load(annotation_file)	#loading the object
        tiers= tgp.TextGrid._find_tiers(par_obj)	#finding existing tiers

        for tier in tiers:

            tier_details = tier.make_simple_transcript()

            for line in tier_details:

                if line[2].find('-y')!=-1:
                    tg_dict['nyas'].append([float(line[0]), float(line[1]),line[2].split('-')[0]])
                else:
                    tg_dict['non-nyas'].append([float(line[0]), float(line[1]),line[2]])

        self.NyasAnnotations = tg_dict

        return True

    def ReadNyasAnnotationsAsList(self, annotation_file):
        """
        Just like ReadNyasAnnotation function but output list instead of dictionary, segments arranged by order to better visualize the similarity matrix
        """
        segment_info=[]

        par_obj = tgp.TextGrid.load(annotation_file)	#loading the object
        tiers= tgp.TextGrid._find_tiers(par_obj)	#finding existing tiers

        for tier in tiers:

            tier_details = tier.make_simple_transcript()

            for line in tier_details:

                if line[2].find('-y')!=-1:
                    segment_info.append([float(line[0]), float(line[1]),'nyas'])
                else:
                    segment_info.append([float(line[0]), float(line[1]),'non-nyas'])

        self.NyasAnnotations = segment_info

        return True


    def removeTrivialSegments(self,pfile):

        #using PitchProcessing class to read pitch data
        ph_obj = PitchProcessing(pitchfile = pfile)

        pitch_presence = np.ones(ph_obj.timepitch[:,1].shape[0])
        pitch_presence[np.where(ph_obj.timepitch[:,1]==0)]=0

        for key in self.NyasAnnotations.keys():
            remove_ind=[]
            for i,segment in enumerate(self.NyasAnnotations[key]):
                presence_ratio = np.sum(pitch_presence[int(segment[0]/ph_obj.phop):int(segment[1]/ph_obj.phop)])/(segment[1]/ph_obj.phop-segment[0]/ph_obj.phop)
                if presence_ratio < self.presenceRatioThd:
                    remove_ind.append(i)

            for i in reversed(remove_ind):
                self.NyasAnnotations[key].pop(i)

    def removeTrivialSegmentsFromList(self,pfile, hop=-1):

        if isinstance(pfile,str):
            #using PitchProcessing class to read pitch data
            ph_obj = PitchProcessing(pitchfile = pfile)
            pitch_presence = np.ones(ph_obj.timepitch[:,1].shape[0])
            pitch_presence[np.where(ph_obj.timepitch[:,1]==0)]=0
            hop = ph_obj.phop
        else:
            pitch_presence = np.ones(pfile[:,1].shape[0])
            pitch_presence[np.where(pfile[:,1]==0)]=0

        remove_ind=[]

        for i,segment in enumerate(self.NyasAnnotations):
            presence_ratio = np.sum(pitch_presence[int(segment[0]/hop):int(segment[1]/hop)])/(segment[1]/hop-segment[0]/hop)
            if presence_ratio < self.presenceRatioThd:
                remove_ind.append(i)

        for i in reversed(remove_ind):
            self.NyasAnnotations.pop(i)

    def removeSegmentsWithSilence(self,timePitch, hop, segments):

        pitch_presence = np.ones(timePitch[:,1].shape[0])
        pitch_presence[np.where(timePitch[:,1]==0)]=0

        remove_ind=[]

        for i,segment in enumerate(segments):
            presence_ratio = np.sum(pitch_presence[int(segment[0]/hop):int(segment[1]/hop)])/(segment[1]/hop-segment[0]/hop)
            if presence_ratio < self.presenceRatioThd:
                remove_ind.append(i)

        #for i in reversed(remove_ind):
            #segments = np..delete(i)
        segments = np.delete(segments,remove_ind,0)
        return segments


class melodySegmentation():
    def __init__(self):
        print 'Initializing melodySegmentation class'
        
    def ExtractBreathPhrases(self, pCents, phop, valid_pause_dur):
        """This function output breath phrases
        """

        # extracting indexes where there is silence in the pitch
        ind_silence = np.where(pCents<=-4000)[0]
        
        #create a array with 0 where there is no silence and 1 where there is silence
        local_pitch = 0*pCents
        local_pitch[ind_silence] = 1

        #Median filter local_pitch arary to remove short silence sections
        ###NOTE: This operation takes care that breathphrases are not broken at short pauses
        #valid_pause_dur = 0.05 #seconds
        samples_pause = int(valid_pause_dur/phop)
        median_length = 2*samples_pause # to remove a block with samples_pause length we need to have length of the filter as 2*samples_pause
        local_pitch = filters.median_filter(local_pitch,size= median_length)

        #extracting change points        
        changepoints = (np.where(local_pitch[1:]-local_pitch[:-1]!=0)[0]) + 1
        changepoints = np.append(0,changepoints)
        changepoints = np.append(changepoints, local_pitch.shape[0]-1)
        
        BreathPhrases = []
        pointer =0
        phrase_cnt=1
        #print len(changepoints)
        while pointer<len(changepoints)-1:
            #print pointer
            if local_pitch[changepoints[pointer]] == 1:
                BreathPhrases.append([changepoints[pointer+1], changepoints[pointer+2]-1, phrase_cnt])
                pointer +=3
                phrase_cnt+=1
            elif local_pitch[changepoints[pointer]] == 0:
                BreathPhrases.append([changepoints[pointer], changepoints[pointer+1]-1,phrase_cnt])
                pointer +=2
                phrase_cnt+=1
        return BreathPhrases
      
    def segmentPitchPLS(self, pCents, hopSize, maxAbsError):
        """
        This function uses PLS segmentation method propose by Keogh. The implementation of the method is the one by Joan serra. He gave me this for nyas identification baseline.
        """
        segObj = pls.piecewise_linear_segmenter(pCents)
        segObj.do_segmentation(absolute_max_error = maxAbsError)
        segments = segObj.get_segments()
        segmentationOutput=[]
        for segment in segments:
            segmentationOutput.append([segment['i'], segment['j']+1])

        segmentationOutput = np.array(segmentationOutput)*hopSize

        return segmentationOutput

    def flatSegmentsPitchVariance(self, pCents, hopSize, varWinLen=100, varThsld=30):
        """
        This function uses just the variance criterion to decide stable melody regions
        varWinLen (ms): window length used for the variance computation
        varThsld (cents): variance threshold used for deciding stable melody regions
        output: 
            time stamps of the melodically stable regions
        """
        var = ComputeLocalVariance(pCents, hopSize, varWinLen)
        indFlat = np.where(var<=varThsld)[0]
        #computing indexes of silence regions
        indSil = np.where(pCents < -5000)[0]    #remember melody is in cents
        indFlat = np.setdiff1d(indFlat, indSil,assume_unique=True)
        flatSegments = groupIndices(indFlat)
        flatSegments =flatSegments

        return flatSegments

    def flatSegmentsSwarVicinity(self, pitch, tonic, hopSize, vicinityThsld = 30):
        """
        This function estimates time regions corresponding to stable melody regions based on vicinity to swar locations. Everything that is under some threshold of a swar location is flat region
        """
        # computing pitch histogram
        phObj = PH.PitchHistogram(pitch, tonic)
        #getting valid swar locations (within one octave)
        phObj.ValidSwarLocEstimation(Oct_fold=1)
        #converting swar locations in indexes to cents
        phObj.SwarLoc2Cents()
        #since the swar locations are computed using octave folded histogram, propagating them to other octaves
        phObj.ExtendSwarOctaves()
        swarCents = phObj.swarCents
        pCents = phObj.pCents
        
        indFlats = np.array([])
        for i, swar in enumerate(swarCents):
            # just to make process fast lets find in one shot all the points which are atleast closer than narrow threshold
            ind_narrow = np.where((pCents<swar+vicinityThsld)&(pCents>swar-vicinityThsld))[0]

            if len(ind_narrow)>0:
                indFlats = np.concatenate((indFlats, ind_narrow))
        flatSegments = groupIndices(indFlats)
        flatSegments =flatSegments
        return flatSegments

    def estimateProbableSegmentationPoints(self, pitch, tonic, hopSize, vicinityThsld = 30, varWinLen=100, varThsld=100):
        """
        This function estimates possible segmentation points for melody. The segmentatino is based on flat notes
        The logic is 
        1) All the within swar vicinity points which have low variance + all the slope change points which are within swar vicinity
        """ 

        pCents = 1200*np.log2((pitch+eps)/tonic)

        ### all the points under variance threshold 
        var = ComputeLocalVariance(pCents, hopSize, varWinLen)
        indFlat = np.where(var<=varThsld)[0]
        #computing indexes of silence regions
        indSil = np.where(pCents < -5000)[0]    #remember melody is in cents
        indVar = np.setdiff1d(indFlat, indSil,assume_unique=True)

        ### index of slope change
        #diff1 = pCents[2:]-pCents[1:-1]
        #diff2 = pCents[1:-1] - pCents[:-2]
        #indSlope = 1 + np.where(diff1*diff2<0)[0]
        ########################
        ###delete this line SOON
        ########################
        #indSlope = np.concatenate((indSlope,indSlope+1))


        ### all the points within the vicinity
        # computing pitch histogram
        phObj = PH.PitchHistogram(pitch, tonic)
        #getting valid swar locations (within one octave)
        phObj.ValidSwarLocEstimation(Oct_fold=1)
        #converting swar locations in indexes to cents
        phObj.SwarLoc2Cents()
        #since the swar locations are computed using octave folded histogram, propagating them to other octaves
        phObj.ExtendSwarOctaves()
        swarCents = phObj.swarCents
        pCents = phObj.pCents
        
        indVic = np.array([])
        indCandidates = []
        for i, swar in enumerate(swarCents):
            # just to make process fast lets find in one shot all the points which are atleast closer than narrow threshold
            ind_narrow = np.where((pCents<swar+vicinityThsld)&(pCents>swar-vicinityThsld))[0]

            if len(ind_narrow)>0:
                #indIntersect = np.unique(np.concatenate((np.intersect1d(indVar, ind_narrow), np.intersect1d(indSlope, ind_narrow))))
                indIntersect = np.intersect1d(indVar, ind_narrow)
                if len(indIntersect)>0:
                    indCandidates.append(indIntersect)
        flatSegments = []
        for segPerSwar in indCandidates:
            flatSegments.extend(groupIndices(segPerSwar))
        
        np.array(flatSegments)
        
        onsets=[]
        for segs in flatSegments:
            onsets.append(segs[0])
            onsets.append(segs[1])

        onsets = np.sort(np.array(onsets))
        return onsets


    def removeOverlapSegsGreedy(self, segments):
        """
        This function computes segments based on greedy search, meaning at each instance selecting segment that is longest.
        """
        length = np.max(segments)
        segLengths = segments[:,1] - segments[:,0]

        decArray = -1*np.ones((length,2))

        for ii, seg in enumerate(segments):
            if np.mean(decArray[seg[0]:seg[1]+1,0])==-1:
                decArray[seg[0]:seg[1]+1,0] = ii
            elif np.mean(decArray[seg[0]:seg[1]+1,1])==-1:
                decArray[seg[0]:seg[1]+1,1] = ii
            else:
                print "I never expected this to happen check around segment index %d"%seg[0]

        finalDecArray = -1*np.ones(length)

        for ii in range(len(finalDecArray)):
            indNeg = np.where(decArray[ii,:]==-1)[0]
            if len(indNeg)==2:
                finalDecArray[ii]=-1
            elif len(indNeg)==1:
                finalDecArray[ii]= decArray[ii,abs(1-indNeg).astype(np.int)]
            else:
                indMax = np.argmax(segLengths[decArray[ii,:].astype(np.int)])
                finalDecArray[ii] = decArray[ii,indMax]

        segmentsOut = []
        for ii in range(segments.shape[0]):
            indSeg = np.where(finalDecArray==ii)[0]
            if len(indSeg)>0:
                segmentsOut.append([indSeg[0], indSeg[-1]])

        segmentsOut = np.array(segmentsOut)
        #checking if there is no overlap in the segments
        indSort = np.argsort(segmentsOut[:,0])
        segmentsOutSort = segmentsOut[indSort]
        diff = segmentsOutSort[1:,1]-segmentsOutSort[:-1,1]
        indNeg = np.where(diff<0)[0] +1
        if len(indNeg)>0:
            print "We still get overlapping segments, something is wrong"
            print segmentsOutSort[indNeg[0]-2,:]
            print segmentsOutSort[indNeg[0]-1,:]
            print segmentsOutSort[indNeg[0],:]
            print segmentsOutSort[indNeg[0]+1,:]
            print segmentsOutSort[indNeg[0]+2,:]
            
        else:
            return segmentsOutSort

    def segmentPitchNyas(self, pitch, tonic, phop, vicinityThsld = 30, varWinLen=100, varThsld=100, timeAwayThsld=100, min_nyas_duration=150.0):
        """
        This function is an improved version of the segmentPItch function in nyasSegmentation class. Here we resolve overlapping flat candidates better and also postprocess nyas candidates to have boundaries as the probably segmentation candidates computed using heuristic based logic

        """
        nyasSegObj = nyasSegmentation()
        nyasSegObj.ComputeNyasCandidates(pitch, tonic, phop, vicinityThsld = vicinityThsld, timeAwayThsld = timeAwayThsld, varianceWinLen = varWinLen, varianceThsld = varThsld)
        nyasSegObj.FilterNyasCandidates(min_nyas_duration=min_nyas_duration)

        segmentationOutput = []

        for key in nyasSegObj.nyasInfo.keys():
            for segment in nyasSegObj.nyasInfo[key]:
                segmentationOutput.append(segment)

        segmentationOutput = np.array(segmentationOutput)
        #Note that these segments are the flat regions only. We need to generate all segments. But to do that we have to make sure there is no overlapping segments
        flatSegments = self.removeOverlapSegsGreedy(segmentationOutput)
        segPoints = self.estimateProbableSegmentationPoints(pitch, tonic, phop, vicinityThsld = vicinityThsld, varWinLen=varWinLen, varThsld=varThsld)
        finalFlatSegs = []
        for ii, flatSegs in enumerate(flatSegments):
            #print len(segPoints[:,0]), len(segPoints[:,1]), flatSegs[0], flatSegs[1]
            indStart = np.where(segPoints>=flatSegs[0])[0]
            indStart2 = np.argmin(abs(segPoints-flatSegs[0]))
            abs_diff = abs(segPoints[indStart2]-flatSegs[0])
            # if the nearest grid point is very close select that, otherwise the next one to start the segment
            if abs_diff <= 2 :
                indStart = np.append(indStart, indStart2)

            indEnd = np.where(segPoints<=flatSegs[1])[0]
            indEnd2 = np.argmin(abs(segPoints-flatSegs[1]))
            abs_diff = abs(segPoints[indEnd2]-flatSegs[1])
            if abs_diff <= 2:
                indEnd = np.append(indEnd, indEnd2)
            indOverlap = np.intersect1d(indStart, indEnd)
            indOverlap = np.sort(indOverlap)
            if len(indOverlap)>0:
                finalFlatSegs.append([segPoints[indOverlap[0]], segPoints[indOverlap[-1]]])
            #if len(indStart)>0 and len(indEnd)>0:
            #    s = max(indEnd)
            #    e = min(indStart)
            #    if  e > s:
            #        finalFlatSegs.append([s,e])

        return np.array(finalFlatSegs)






