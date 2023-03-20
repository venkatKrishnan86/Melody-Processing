import numpy as np
import scipy.signal as sig
import math
eps = np.finfo(np.float).eps
min_pitch = 60	#Hz, humanly not possible below this
import sys, os
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
sys.path.append(os.path.join(os.path.dirname(__file__), './backgroundFunctions'))
import warnings
warnings.filterwarnings("ignore")
import basicOperations as BO
import batchProcessing as BP
import pitchHistogram as PH
import segmentation as seg
import transcription as ts
import pitchPostProcess as PP
import copy
import pickle
pwd = os.path.dirname(__file__)  
  
  
def main(pwd):
  """
  """  

  generate_file_list(pwd)
  batch_proc('fileList.txt')
  writeTranscriptionHz('fileList.txt')
  

def batch_proc(fileList, pitchExt = '.pitch', tonicExt = '.tonic', transExt = '.transcription'):
  """
  """
  lines = open(fileList,'r').readlines()
  
  for ii, line in enumerate(lines):
    
    filename = line.strip()
    print "Processing file: %s" %filename
    
    # Read pitch data
    #----------------
    pitch, time, Hop = BO.readPitchFile(filename + pitchExt)
    tonic = np.loadtxt(filename  + tonicExt)
    pcents = BO.PitchHz2Cents(pitch, tonic)
    pdata = (time,pcents,Hop)
    
    # Histogram processing to extract note locations
    #------------------------------------------------
    svaraSemitone, ignoreNotes = findValidSvaras(filename,pitch,tonic)
    
    ## Svara transcription
    #---------------------
    samples, timeSeries, transcription = transcribePitch(filename,pdata,ignoreNotes)
    
    smoothPitch = PP.postProcessPitchSequence(pitch, tonic=tonic, hopSize=Hop, filtDurMed=0.05, filtDurGaus=0.05, winDurOctCorr=0.3, sigmaGauss=0.025, fillSilDur= 0.25, interpAllSil=False, upSampleFactor=1)
    pcents_smth = BO.PitchHz2Cents(smoothPitch, tonic)
    
    # See the transcribed notes
    #--------------------------
    plt.plot((np.arange(len(pcents_smth))*Hop), pcents_smth, 'c-')
    qts = get_quantized_ts(fileList)
    plt.plot((np.arange(len(qts))*Hop), qts, 'r', linewidth=3)
    plt.ylim([-500,1700])
    plt.grid(True)
    #plt.show()
    

def generate_file_list(rootDir):
  """
  """
  fileList = BP.generateFileList((os.path.join(rootDir, 'data')), 'fileList.txt', ext = '.pitch')    
  
  
def findValidSvaras(filename,pitch,tonic):
  """
  """    
  phObj = PH.PitchHistogram(pitch, float(tonic))
  phObj.ComputePitchHistogram(Oct_fold=1)
  phObj.ValidSwarLocEstimation()
  phObj.SwarLoc2Cents()
  svara = phObj.swarCents
  print "Computing svara from histogram..."
  phObj.PlotSwarOnHistogram(filename,showOrSave=1)
  svaraSemitone = map(lambda svara:round(svara,-2),svara)
  octaveNotes = range(0,1101,100)
  ignoreNoteLevels = list(set(octaveNotes).difference(svaraSemitone))
  noteNames = ['S','r','R','g','G','m','M','P','d','D','n','N']
  ignoreNotes = []
  for i in range(len(ignoreNoteLevels)):
    ignoreNotes.append(noteNames[octaveNotes.index(ignoreNoteLevels[i])])        
  return svaraSemitone, ignoreNotes  


def transcribePitch(fname,pdata,ignoreNotes):  
  """
  """
  tsObj = ts.SvarTranscription(pdata)
  samples, timeSeries, transcription = np.array(tsObj.perform_transcription(ignoreNotes, thres=80, width=35, verbose=False)) 
  transcriptionFilename = (''.join([fname,'.transcription']))
  np.savetxt(transcriptionFilename,transcription, delimiter = "\t", fmt="%f\t%f\t%d")
  return samples, timeSeries, transcription


def find_ind(time_stamps, time):
  """
  """
  ind = np.argmin(np.abs(time_stamps-time))
  return ind


def get_quantized_ts(fileList, pitchExt = '.pitch'):
  """
  """
  lines = open(fileList,'r').readlines()
  
  for ii, line in enumerate(lines):
    pitch, time, Hop = BO.readPitchFile(line.strip() + pitchExt)
  
  song_str, st_seg, en_seg = readTransFile(fileList, transExt = '.transcription')
  
  st, en = st_seg/Hop, en_seg/Hop
  
  qts = np.array([None]*(max(en)))
  for ii in range(len(st)):
    qts[st[ii]:en[ii]] = song_str[ii]
  
  return qts     


def readTransFile(fileList, transExt = '.transcription'):
  """
  """
  lines = open(fileList,'r').readlines()
  
  for ii, line in enumerate(lines):
    transcription_filename = line.strip() + transExt
    transcription_file = np.loadtxt(transcription_filename)
    
    song_str = transcription_file[:,2].astype(int)
    st_seg = transcription_file[:,0]
    en_seg = transcription_file[:,1]   
    
  return song_str, st_seg, en_seg


def writeTranscriptionHz(fileList, tonicExt = '.tonic', transExt = '.transcription', outfileExt = '.transcription_Hz'):
  """
  """
  lines = open(fileList,'r').readlines()
  
  for ii, line in enumerate(lines):
    tonic = np.loadtxt(line.strip() + tonicExt)
    
    transcription_filename = line.strip() + transExt
    transcription_file = np.loadtxt(transcription_filename)
    song_str = transcription_file[:,2]
    
    note_Hz = tonic*np.power(2,song_str/1200)
    
    output = []
    for ii, note in enumerate(song_str):
      output.append([transcription_file[ii,0], transcription_file[ii,1], song_str[ii], note_Hz[ii]]) 
    
    transcription_Hz_filename = line.strip() + outfileExt
    np.savetxt(transcription_Hz_filename,output, delimiter = "\t", fmt="%f\t%f\t%d\t%f")



if __name__ == '__main__':
  main(pwd)