Audio signal processing for melodic analyses in Indian art music
================================================================
Author: Kaustuv Kanti Ganguli
Date: June 13th, 2016
Contact: +919769753366
==============================

-----------------------------------------------------------------------------------------------------------------------
For visualizing the melodic contour and the automatically extracted sargam notation, please follow the following steps:
-----------------------------------------------------------------------------------------------------------------------
1) Navigate to the directory '<current_folder>/data/<album>/'
2) Load the audio (.mp3) file to Sonic Visualizer
3) Load the pitch (.pitch) file to Sonic Visualizer
4) Load the transcription (.transcription_Hz) file to Sonic Visualizer. There are four columns to be loaded. Change the third column type to 'Label' from the dropdown menu, and keep the rest as default. Change the scale to 'Auto-Align' from the dropdown menu on the right pane. Now, you will see horizontal bars aligned to the pitch contour with labels 100*n, where n is an integer. These correspond to the 12 notes of the octave. The mapping is defined below.
Label: -200	-100	0	100	200	300	400	...	1200	1300	1400
Notes: _n	_N	S	r	R	g	G	...	S_	r_	R_


-------------------------------------------------------------------------------------------
To extract the same information for an unknown song, please follow the following steps:
-------------------------------------------------------------------------------------------
1) Create a sub-directory '<current_folder>/data/<new_album>/'
2) Add the audio (.mp3) file to the same directory with a filename with no white spaces (you can follow the convention 'initial_raga')
3) Extract the pitch from Melodia and save the patch file in the same directory as <filename>.pitch (the filename should be same as above)
4) Find the tonic of the piece by hearing and create a file with the name <filename>.tonic with the frequency in Hz. You can use the internet to find the frequency chart (http://www.phy.mtu.edu/~suits/notefreqs.html). Please check the correctness of the tonic with the help of a website (http://onlinetonegenerator.com/) by simultaneously playing the audio and the tone. The precision of the tonic value will matter for the rest of the analyses.
5) On your system, please install python 2.7, numpy, scipy, matplotlib. There are no other major dependencies, please write to me if you get an error in the next step. We can resolve them by mail/phone conversation.
6) Open terminal and navigate to the directory where you have unzipped this package (the folder where master.py is located). Type "python master.py" without quotes and press 'Enter'. This will run the analyses for all artists at one go, hence you are requested to add as many artists you want as per guidelines above and run the code only once, at the very end.
7) This will generate the transcription (.transcription_Hz) file within each album, you can further observe them on Sonic Visualizer.
8) This will also generate the pitch histogram (<filename>_histogram.pdf) file which you can make inference from. E.g., you will see that the spread of each peak (corresponding to a note) is different. In KA_Bhoop you can observe the peak location of 'G' is lower than the equi-tempered grid (400 cents) and the valley for 'M' is not as deep as one would expect for a non-raga note. These explains the average intonation of 'G' and presence of 'M' touch note by the artist. You can make many interesting observations from the histogram specially if you have pieces of allied ragas, say you can compare Bhoop-Deshkar-SudhKalyan or Puriya-Marwa-Sohini etc.


-------------------------------------------------------------------------------------------
Improvement in Automation done by - Venkatakrishnan V K
1. Eliminated requirement of inputting '.pitch' and '.tonic' files (Automatically calculates internally in the code)
2. Simplified the whole process to running two blocks in: https://colab.research.google.com/drive/1mpEfOCgt_0m5T2jNEfGIPWkrPKsqxNbm#scrollTo=FNItTLflYBXG
