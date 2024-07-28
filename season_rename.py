import datetime
from time import strftime
import os, sys, glob, re
from pickle import NONE
import time
from optparse import OptionParser

try: #pip install ffmpeg-python
    import ffmpeg
    bool_ffmpeg = True
except:
    bool_ffmpeg = False
    print("ffmpeg-python not installed")

folder = r"" #autodetect show and season TV_Title_SEASON_2_DISC_1. prompt to add year and record for future discs
title = "" #show title
season = 1
episode = 1
special = 1 #do no reset this value between seasons. tracking dict based on title? Scan feature to get current location?
bool_bluray = False
bool_title_filename = True
bool_title_autodetect = True #autopopulate title based on folder name
bool_continue = True #track episodes and continue numbering from last disk
bool_multi_episode_detect = True #handle multiple episodes existing in one file along side single episodes
bool_detect_e_count = True #dynamically detect the episode count. False assumes only two episodes max
multi_episode_parts = False #assumes you have removed all non-episode files from the folder and will mark short episodes as parts sbsp. Need to track short episode time adding them up until we get a whole one
bool_prevalence = False # Use prevlance to identify specials
bool_low_prev_special = True # large files that have a low size prevalence are marked as a special
bool_mtime = True #use the OS filesystem modified time to sort the files
bool_reverse = False #reverse the file sort for naming. Default: False
bool_force_all = False #testing only
bool_verbose = False #output length and time diff


## -- INI List Loader -- ##
def get_ini_value(inifilepath, iniSection, inikey, default_value):
    if os.path.exists(inifilepath) == False:
        #print("File does not exist: " + inifilepath)
        return ""
    with open(inifilepath) as fp:
        line = "initialize"
        boolCollect = False
        while line:
            line = fp.readline()

            if ("[" + iniSection + "]") in line:
                boolCollect = True
            elif line[0:1] =="[":
                boolCollect = False
            elif boolCollect == True:
                key = f"{inikey}="
                if f"{inikey}=" in line:
                    valuestart = line.find("=")
                    keyValue = line[valuestart +1:]
                    return keyValue.replace("\n","")
        return default_value



   
  

#todo or dismiss since switching to time based assessments. These clipping levels need to be dynamic based on the size of the files presented
if bool_bluray == False:
  extras_clipping_size = 908374890
  clipping_variance = 45000000 #45MB
else:
  extras_clipping_size = 1520754951
  clipping_variance = 450000000 #450MB


extras_clipping_length = "" #may make sense to prompt for this item "00:18:00". This is the length of the episode
new_clipping_length = "00:24:00" #may make sense to prompt for this item in "bool_ffmpeg for i == " fallback loop "00:43:00"
clipping_time_variance = 178 #seconds
new_clipping_time_variance = 690 #seconds
f_time = "%H:%M:%S" #"01:02:03"


def build_cli_parser():
    parser = OptionParser(usage="%prog [options]", description="Rename season episodes in a directory")
    parser.add_option("-d", "--directory", action="store", default=None, dest="folder",
                      help="Folder path to directory containing episodes")
    parser.add_option("-l", "--length", action="store", default=None, dest="episode_len",
                      help="Roughly how long are episodes. Takes format HH:MM:SS")
    parser.add_option("-n", "--new", action="store_true", default=None,
                      help="New show (not continuing the previous one)")
    parser.add_option("-o", "--out", action="store", default=None, dest="outlocation",
                      help="Output location")
    parser.add_option("-t", "--title", action="store", default=None, dest="title",
                      help="Title the episode with this string of text")
    parser.add_option("-s", "--season", action="store", default=None, dest="season",
                      help="Season number")
    parser.add_option("-v", "--variance", action="store", default=None, dest="variance",
                      help="Largest variance in seconds between episode lengths")
    return parser

parser = build_cli_parser()
opts, args = parser.parse_args(sys.argv[1:])
if opts.folder:
  folder = opts.folder
if folder == "":
    folder = input("Enter your folder path: ")
if opts.episode_len:
  extras_clipping_length = opts.episode_len
if opts.new:
  bool_continue = False
if opts.outlocation:
    out_location = opts.outlocation
    print(f"output to: {out_location}")
    from pathlib import Path
    if not os.path.exists(out_location ): 
        Path(out_location).mkdir(parents=True, exist_ok=True)
else:
    out_location = folder
if opts.title:
   title = opts.title
   title = title.replace("<","").replace(">","").replace("\"","").replace("/","").replace("|","").replace("?","").replace("*","").replace(":"," -")#remove invalid chars
if opts.season:
   season = opts.season
if opts.variance:
   variance = opts.variance
   if variance.isnumeric():
    clipping_time_variance = int(variance)


def is_play_all(time_length, list_size, list_time, str_episode, episode): #simple code to detect playall mixed with individual episodes
    episode_times = None
    ecount = 0
    e_count = episode - int(str_episode) + 1
    bool_timematch = False
    for e_time in list_time:
        if time_length != e_time:
            ecount +=1
            if ecount > e_count:
               break
               
            if episode_times == None:
                episode_times = get_time_seconds(e_time)
            else:
                episode_times += get_time_seconds(e_time)
        elif bool_timematch == False:
           bool_timematch = True
        else:
           return False #multiple episodes with the same length means this is not playall
    if episode_times == None:
        return False
    episode_seconds = get_time_seconds(time_length)
    if get_diff(episode_seconds, episode_times) < clipping_time_variance *2:
        return True
    else:
        return False
    

if len(extras_clipping_length) < 8: #we do not have the right time format but lets try to fix or give feedback
   if extras_clipping_length.find(":") > -1:
      print(extras_clipping_length[:extras_clipping_length.find(":") ])
      first_colon = extras_clipping_length.find(":")
      if  first_colon !=  extras_clipping_length.rfind(":"): #we have a second colon
         second_colon = extras_clipping_length.rfind(":")
         if first_colon == 0:
            extras_clipping_length = f"00{extras_clipping_length}"
         if first_colon == 1:
            extras_clipping_length = f"0{extras_clipping_length}"
         second_colon = extras_clipping_length.rfind(":") #refresh where the second colon is
         if second_colon == 3:
            extras_clipping_length = f"{extras_clipping_length[:2]}00{extras_clipping_length[3:]}"
         if second_colon == 4:
            extras_clipping_length = f"{extras_clipping_length[:2]}0{extras_clipping_length[3:]}"
         if second_colon == len(extras_clipping_length) -1:
            extras_clipping_length = f"{extras_clipping_length}00"
         if second_colon ==len(extras_clipping_length) -2:
            extras_clipping_length = f"0{extras_clipping_length}0"
      else: #single colon
         minutes, seconds = extras_clipping_length.split(":")
         if minutes.isnumeric() and seconds.isnumeric():
            if (minutes == 1): # hour long episode - minutes are hours
               extras_clipping_length = extras_clipping_length + ":00"
            else: #minutes are minutes
               extras_clipping_length = "00:" + extras_clipping_length
            
         
   elif extras_clipping_length.isnumeric():
      str_clip_minutes = extras_clipping_length
      int_clip_minutes = int(extras_clipping_length)
      if int_clip_minutes >59:
         print("provide hours and minutes in colon form hh:mm")
         quit()
      extras_clipping_length = f"00:{str_clip_minutes}:00"
      
def get_time_seconds(time1):
    return datetime.timedelta(hours=time1.tm_hour,minutes=time1.tm_min,seconds=time1.tm_sec).total_seconds()
#new code to dynamically assign a variance when episode length is specified
if not opts.variance and opts.episode_len:
    tmp_tobj = time.strptime(extras_clipping_length, f_time) #'00:42:19'
    int_tmp_seconds = get_time_seconds(tmp_tobj)
    clipping_time_variance = round(int_tmp_seconds / 8)

if extras_clipping_length == "":
    #extras_clipping_length = input("Enter time HH:MM:SS ")
    extras_clip_time = time.strptime("00:18:00",f_time)
else:
    extras_clip_time = time.strptime(extras_clipping_length,f_time)

if not os.path.exists(folder):
   print(f"folder path does not exist: {folder}")
   quit()

def query_yes_no(question, default="yes"):#https://stackoverflow.com/questions/3041986/apt-command-line-interface-like-yes-no-input
    """Ask a yes/no question via raw_input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
            It must be "yes" (the default), "no" or None (meaning
            an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True, "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        sys.stdout.write(question + prompt)
        choice = input().lower()
        if default is not None and choice == "":
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' " "(or 'y' or 'n').\n")


def Middle(lst):
   int_low = lst[0]
   int_high =lst[0]
   for int_num in lst:
      if int_num > int_high:
         int_high = int_num
      elif int_num < int_low:
         int_low = int_num
   return Average([int_low, int_high])
         

# Python program to get average of a list 
def Average(lst):
    if lst:
        return sum(lst) / len(lst) 

def get_diff(int1, int2):
    if int1 > int2:
       return int1 - int2
    else:
       return int2 - int1


    
def get_time_diff(time1, time2):
    int_t1 = datetime.timedelta(hours=time1.tm_hour,minutes=time1.tm_min,seconds=time1.tm_sec).total_seconds()
    int_t2 = datetime.timedelta(hours=time2.tm_hour,minutes=time2.tm_min,seconds=time2.tm_sec).total_seconds()
    if int_t1 > int_t2:
       return int_t1 - int_t2
    else:
       return int_t2 - int_t1    

def logToFile(strfilePathOut, strDataToLog, boolDeleteFile, strWriteMode):
    with open(strfilePathOut, strWriteMode) as target:
      if boolDeleteFile == True:
        target.truncate()
      target.write(strDataToLog + "\n")
  


#MAIN FUNCTION
def episode_rename(folder, season,extras_clipping_size, extras_clip_time, clipping_time_variance, title, episode,special,out_location):
    global os,bool_ffmpeg, bool_title_filename,bool_bluray,bool_prevalence,new_clipping_length
    #find the largest file and then find the lowest file size within 45 MB of it and then see if prevalence has a lower threshold (bonus extras can be longer/bigger than the episode throwing everything off)
    upper_size = extras_clipping_size
    lower_size = extras_clipping_size
    upper_length =  extras_clip_time
    lower_length = extras_clip_time
    list_size = []
    list_time = []
    dict_time = {} #filepath:timeobject
    for filename in os.listdir(folder):
      file_location = os.path.join(folder, filename)
      size = os.path.getsize(file_location)
      list_size.append(size)
      if size < lower_size:
         lower_size = size
      if size > upper_size:
         upper_size = size
      if bool_ffmpeg:
        try:
            metadata = ffmpeg.probe(file_location)["streams"]
        except:
           metadata = ""
           print("Failed to probe media using ffmpeg. Do you have the binaries installed?")
           bool_ffmpeg = False
        if len(metadata) > 0 and 'tags' in metadata[0]:
            language = metadata[0]['tags']['language']
            length = metadata[0]['tags'][f'DURATION-{language}']
            t_len = time.strptime(length[0:length.find(".")], f_time) #'00:42:19.003133333'
            list_time.append(t_len)
            dict_time[file_location] = t_len #store the file location time pair for lookups later
            if t_len < lower_length:
                lower_length = t_len #set lowest size
            if t_len > upper_length:
                upper_length = t_len #set largest size
    average = Average(list_size)
    if not list_size:
       print("failed to get file listing")
       quit()
    lower_diff = average - lower_size
    upper_diff = upper_size - average
    lower_clip_size =  upper_size
    dict_size_prev = {} #build a dict of prevalence based on clipping size
    dict_length_prev = {} #build a dict of prevalence based on length
    episode_bytes = 0 #track episode byte aggregation for multi-episode file detection
    episode_count = 0 #minus the largest file (used for multi-episode file detection)
    multi_episode = 0 #size of multi-episode identified file
    bool_found_episode = False
    for size in list_size:
      #if greater than average and within 45MB of another file
        if size > average or get_diff(size, average) < clipping_variance:
            for tmp_size in list_size:
               if get_diff(size, tmp_size) < clipping_variance:
                  if size in dict_size_prev:
                     dict_size_prev[size] +=1
                  else:
                     dict_size_prev[size] =1
        diff = upper_size - size
        if diff < clipping_variance:
            if size < lower_clip_size:
             lower_clip_size = size
        if size > extras_clipping_size:
            bool_found_episode = True
        if upper_size != size: #not the largest file
           #add up bytes and see if we get close to the large file.
            episode_bytes += size
            episode_count +=1
           #if so likely multi-episode file/play all 

    if bool_ffmpeg: #time length calculations
        for i in range(0, 3):
            if i == 1:
               if opts.episode_len:
                   break
               extras_clip_time = time.strptime(new_clipping_length,f_time)
               clipping_time_variance = new_clipping_time_variance
               new_clipping_length = "00:43:00"
            if i == 2:
           
               extras_clip_time = time.strptime(new_clipping_length,f_time)
               clipping_time_variance = new_clipping_time_variance
            bool_found_episode_time = False
    
            int_prevalent = 0 #tracks the highest prevalence
            for t_len in list_time:
                #used to dynamically set extras_clip_time    
                for tmp_t_len in list_time:
                    if get_time_diff(t_len, tmp_t_len) < clipping_time_variance and get_time_seconds(t_len) > clipping_time_variance and get_time_seconds(tmp_t_len) > clipping_time_variance:
                        if t_len in dict_length_prev:
                            dict_length_prev[t_len] +=1 #increase prevalence
                            if dict_length_prev[t_len] > int_prevalent: #if most prevalent then
                                int_prevalent = dict_length_prev[t_len] #record most prevalent size
                        else:
                            dict_length_prev[t_len] =1
                #detect episode
                if get_time_diff(t_len, extras_clip_time) <= clipping_time_variance:
                    bool_found_episode_time = True # detected an episode based on the current clip time and variance
            list_int_seconds = []
            str_clipping_var = str(datetime.timedelta(seconds=clipping_time_variance))
            time_clipping_variance = time.strptime(str_clipping_var,f_time)
            bool_mismatch_length = False #used to handle multiple matching prevalence sets (same prevalence count but different size set)
            for tmp_t_len in dict_length_prev:
            
         
                if dict_length_prev[tmp_t_len] == int_prevalent and tmp_t_len > time_clipping_variance: #prevalence match and length is above clipping variance
                   for tmp_ti_len in dict_length_prev: #only take the larger set
                      if dict_length_prev[tmp_ti_len] == int_prevalent and tmp_ti_len > tmp_t_len and get_time_diff(tmp_ti_len, tmp_t_len) > clipping_time_variance: #if same prevalence and greater in size and outside of variance 
                         bool_mismatch_length = True
                   #append the total seconds to list     
                   list_int_seconds.append(datetime.timedelta(hours=tmp_t_len.tm_hour,minutes= tmp_t_len.tm_min,seconds=tmp_t_len.tm_sec).total_seconds())
            if not list_int_seconds: #no prevalence
                if bool_found_episode_time == True:
                   list_int_seconds.append(datetime.timedelta(hours=extras_clip_time.tm_hour,minutes= extras_clip_time.tm_min,seconds=extras_clip_time.tm_sec).total_seconds())
                else:
                   if i == 1 : #hit second pass and still no hit
                    print("No episode found. Settings may need adjusted or the folder does not contain an episode")
                    quit()

                   elif extras_clipping_length == "": #autodetect
                       new_clipping_time_variance 
                       continue
                   else:
                      continue #no episode match. Try again with different clipping length
            average_seconds = Average(list_int_seconds) #should we just use the lowest and highest value to get in the middle and not skew?
            if bool_verbose:
               print(f"average {average_seconds}")
            average_seconds = Middle(list_int_seconds)
            str_average = str(datetime.timedelta(seconds=average_seconds))
            time_average = time.strptime(str_average[0:length.find(".") -1], f_time) #'00:42:19.003133333'
            if get_time_diff(time_average, extras_clip_time) > clipping_time_variance: #if a great difference between the average and the clip time
        
                if bool_found_episode_time == True and not opts.episode_len: #episode found so prompt prevalence only if no time specified
                    bool_prevalence = query_yes_no(f"The average of the most prevalent video length was outside of the clipping level. Would you like to set the episode length to {str_average}?")
                elif not opts.episode_len:
                   bool_prevalence = True #no episode found so auto-attempt prevalence
                if bool_prevalence:
                   if time_average > extras_clip_time and bool_mismatch_length == False:
                    extras_clip_time = time_average
                    break
                   else:
                      print(f"adjusting episode length to {new_clipping_length}")
                      continue
                else:
                    break
            else:
                break

    #---- end size and length calculations -----


    if bool_found_episode == False and (bool_found_episode_time == False or not bool_ffmpeg) and bool_prevalence == False: #used for file size episode autodetect
       bool_prevalence = query_yes_no("No epsisodes found. Would you like to attempt automatic identification?")
    else: #size limit should have triggered a multi-episode so else here
       large_vs_agg_diff = get_diff(upper_size,episode_bytes)
       size_compare = (episode_count * clipping_variance) #could probably hard code a value but this dynamic method seems neat
       if large_vs_agg_diff < size_compare and size_compare > episode_bytes and episode_count > 1:
          multi_episode = upper_size
    if bool_prevalence == True: # Use prevalence to identify specials

        prevalence = 1
        for size in dict_size_prev:
           if dict_size_prev[size] > prevalence:
              prevalence = dict_size_prev[size]
        for size in dict_size_prev:
            if dict_size_prev[size] == prevalence:   
                if size < lower_clip_size:
                 lower_clip_size = size
        extras_clipping_size = lower_clip_size -2
    else:
       bool_low_prev_special = False
    #need to take arguments to overwrite epsisode number in case of skipped/failed expisode


    #function to create season string
    def disc_num(disc_id, str_f_name):
        if str_f_name[0] == "_": #strip leading underscore
            str_fname = str_f_name[1:]
        else:
           str_fname = str_f_name
        if disc_id in str_fname: #
           str_number = "identification"
           tmp_season_lable = str_fname[str_fname.rfind(disc_id):]
           if len(tmp_season_lable) > 1:
              str_number = tmp_season_lable[len(disc_id)]
              if str_number == " ": #if space then move to next character
                disc_id = disc_id + " "
                if len(tmp_season_lable) > len(disc_id):
                    str_number = tmp_season_lable[len(disc_id):]
           if str_number.isnumeric() and len(tmp_season_lable) > len(disc_id) + 1:
              tmp_second_char = tmp_season_lable[len(disc_id)+1]
              if tmp_second_char.isnumeric():
                str_number = str_number + tmp_second_char
           if str_number.isnumeric():
              return int(str_number)
           elif tmp_season_lable[3:].find(disc_id) > 0:
            return disc_num(disc_id, tmp_season_lable[3:]) 
        return(-1) 

    bool_season_disc_match = False
    str_season = ""
    auto_title = ""
    bool_season_prompt = False
    if bool_continue == True:

      #grab season from folder name
      #if season and season != ini loaded season
      #check file name before season and if same as ini then load title from INI
      bool_reset = False
      bool_season_match = False
      tmp_title = get_ini_value("config.ini", "season_rename", "title", title)
      tmp_dir = get_ini_value("config.ini", "season_rename", "dir", "")
      str_season_match = "_S"
      if "_S" in folder:
         str_season_match = "_S"
         if "_Season_" in folder:
            str_season_match = "_Season_"
         if "_SEASON_" in folder:
            str_season_match = "_SEASON_"
      elif "Season " in folder:
         str_season_match = "Season "
      elif "SEASON " in folder:
         str_season_match = "SEASON "
      elif " S" in folder:
         str_season_match = " S"
      elif " s" in folder:
         str_season_match = " s"
      elif "S" in folder:
         str_season_match = "S"
      elif "s" in folder:
         str_season_match = "s"
      int_part = disc_num("P", folder) # some shows do parts instead of seasons
      if str_season_match in folder: #Attempt to auto detect season from folder name
           offset = 0 #utilized for _S1D1 vs. _S1_D1
           str_season = "season identification"
           tmp_season_lable = folder[folder.find(str_season_match):]
           
           if len(tmp_season_lable) > len(str_season_match) +3:
              str_season = tmp_season_lable[len(str_season_match): len(str_season_match)+1]
           if len(tmp_season_lable) == len(str_season_match) +3:
              str_season = tmp_season_lable[len(str_season_match): len(str_season_match)+1]
           if not str_season.isnumeric() and len(tmp_season_lable) > len(str_season_match) +1:
              str_season = tmp_season_lable[1:2]
           if not str_season.isnumeric():
               offset = 1 #_S1_D1
               if len(tmp_season_lable) >  len(str_season_match)+offset+1:
                str_season = tmp_season_lable[len(str_season_match)+offset: len(str_season_match)+offset+1]
           if str_season.isnumeric():
            tmp_compare_dir = os.path.basename(folder)
            tmp_compare_dir = tmp_compare_dir[:tmp_compare_dir.find(f"_S{str_season}")]
            if tmp_compare_dir == tmp_dir[:tmp_dir.find(str_season_match)]: #exact folder match means retain title from ini
               title = tmp_title
           if str_season.isnumeric() and len(tmp_season_lable) >= len(str_season_match)+offset +4:
              tmp_second_char = tmp_season_lable[len(str_season_match)+offset +1:len(str_season_match)+offset + 2]
              if tmp_second_char.isnumeric():
                str_season = str_season + tmp_second_char        
      elif not str_season.isnumeric() and int_part.isnumeric(): # using parts instead of seasons
         str_season=int_part

      if str_season.isnumeric():
         if bool_title_autodetect == True:
            auto_title = folder[folder.rfind("\\")+1:folder.rfind(str_season_match)]

      
      if bool_season_prompt == True:
        str_season = input("What is the season number?")
        print(str_season)

              
      else:
         result = re.search(r"s(\d{1,2})d\d", folder)
         if result: #regex found season number
            str_season = result.group(1)
            if title == "" and bool_title_autodetect == True:
               auto_title = folder[folder.rfind("\\")+1:folder.find(result.group(0))]

      def rreplace(s, old, new, occurrence):
        if old == '':
            return s
        li = s.rsplit(old, occurrence)
        return new.join(li)

      

      str_truncate = "Disc "
      int_disc = disc_num(str_truncate, folder)
      if int_disc < 0:
         str_truncate = "Disc"
         int_disc = disc_num(str_truncate, folder)
      if int_disc < 0:
         str_truncate = "DISC"
         int_disc = disc_num(str_truncate, folder)
      if int_disc < 0:
         str_truncate = "DISC_"
         int_disc = disc_num(str_truncate, folder)
      if int_disc < 0:
         str_truncate = "Disc_"
         int_disc = disc_num(str_truncate, folder)
      if int_disc < 0:
        int_disc = disc_num("_D", folder)
        str_truncate = "_D"
      if int_disc < 0:
        int_disc = disc_num("D", folder)
        str_truncate = "D"
      if int_disc < 0:
        int_disc = disc_num("d", folder)
        str_truncate = "d"
      if int_disc < 0:
        int_disc = disc_num("BD", folder)
        str_truncate = "BD"
        
      if int_disc > 0: #the following variables will be used at the end to determine if the next disc is available for autocontinue
          next_disc = int_disc+1
      elif season > 0:#single disc season
          next_season_folder = rreplace(folder,str_season, str(season +1),1) 
      if int_disc < 0: #failed to identify disc
          next_disc = -1

      if int_disc > 0 and title == "" and bool_title_autodetect == True and auto_title == "": #one last attempt to autotitle
         auto_title = folder[folder.rfind("\\")+1:folder.find(f"{str_truncate}{int_disc}")]
         auto_title = auto_title.strip()
      if len(auto_title) > 4:
        if auto_title[-3:] == " - ": #we add this exact string after the title. No reason to duplicate it
            auto_title= auto_title[:-3]
        if auto_title[-2:] == " -": #we add this exact string after the title. No reason to duplicate it
            auto_title= auto_title[:-2]
        if auto_title[-1] == "_":
            auto_title = auto_title[:-1] #remove trailing underscore
        if "_ " in auto_title: #unwanted underscore
           auto_title = auto_title.replace("_ ", " ")
        if tmp_title == auto_title: #continue using the same title
            title = tmp_title    

      if ((title != "" and tmp_title != title) or (bool_title_autodetect and auto_title != "" and tmp_title !=auto_title.strip())) and episode == 1:
        print("title mismatch. Resetting episode number to start at 1")
        bool_reset = True
        episode = 1
        if str_season.isnumeric():
          season = int(str_season)
        special = 1
      else:

         if int_disc > 0:
            tmp_dir = get_ini_value("config.ini", "season_rename", "dir", title)
            int_old_disc = disc_num("D", tmp_dir)
            if int_old_disc > -1 and int_disc > int_old_disc:
                print("Season next disc match")
                bool_season_disc_match = True
                bool_season_match = True
            
         if bool_season_disc_match == False: #not next disc in season
            if str_season.isnumeric(): #if we have a season identified use that
                season = int(str_season)
            
#if bool_season_prompt == True and int_disc > 1 and episode == 1: #not first disc but we are at first episode
#There is no way to know if we are at the right episode number unless we are at season 1 disc 1
# if disc >1 and episode > 1 then this is likely a continuation of the same season and no need to prompt
      dir_name = ""
      if "\\" in folder:
        dir_list = folder.split("\\")
        dir_name = dir_list[-1]
        tmp_val = get_ini_value("config.ini", "season_rename", "dir", "") #get path from ini
        if len(tmp_val) > 1 and tmp_val[0:len(tmp_val) -1] in dir_name: #one char diff
           bool_season_match = True
  
      #Think it is best to add arg for a season number and check here if one was provided to force a season match otherwise ignore this match
      if opts.season and (f"s{season}" in folder.lower() or f"s0{season}" in folder.lower() or f"season {season}" in folder.lower()):
        print("season match")
        bool_season_match = True
    

      if bool_season_match and not bool_reset:
        tmp_val = get_ini_value("config.ini", "season_rename", "special", special)
        if tmp_val.isnumeric():
            special = int(tmp_val) #never reset special numbering if we are on the same show
        tmp_val = get_ini_value("config.ini", "season_rename", "season", season)
        if tmp_val.isnumeric():
            tmp_val = int(tmp_val)
        if tmp_val == season or bool_season_disc_match: #same season
            if bool_season_disc_match:
               season = tmp_val
            tmp_val = get_ini_value("config.ini", "season_rename", "episode", episode)
            if tmp_val.isnumeric():
               episode = int(tmp_val)
            bool_title_filename = get_ini_value("config.ini", "season_rename", "bool_title_filename", bool_title_filename)
            if bool_title_filename == True:
               title = get_ini_value("config.ini", "season_rename", "title", title)
            bool_bluray = get_ini_value("config.ini", "season_rename", "bool_bluray", bool_bluray)
      elif bool_reset: #
    
        if title == "":
            if bool_title_autodetect and auto_title != "":
               title = auto_title
               bool_title_prompt = False
            else:
               bool_title_prompt = True
            tmp_title = get_ini_value("config.ini", "season_rename", "title", title)
            subpath = tmp_title[0:-5]
            if subpath in folder:
                bool_title_prompt = False
                list_split_chars = [" ", "_", "-"]
            if bool_title_prompt == False and " " in tmp_title:
                list_title_label = tmp_title.split(" ")[0]
                if list_title_label[0] in folder.lower():
                 bool_title_prompt = False
            if bool_title_prompt == True:

               title = input("What is the title?")
               print(title)

   
    title = title.strip()
    def format_season_episode_num(int_numeric):
        str_numeric = str(int_numeric)
        if len(str_numeric) == 1:
            str_numeric = f"0{str_numeric}"
        return str_numeric

    str_folder_pt1 = folder[0:folder.rfind(str_truncate)]
    next_season_folder = rreplace(str_folder_pt1, str_season, str((season +1)),1) + rreplace(folder[folder.rfind(str_truncate):], str(int_disc),"1",1)
    str_folder_pt2 =  rreplace(folder[folder.rfind(str_truncate):],str(int_disc),str(next_disc),1)
    next_folder = f'{str_folder_pt1}{str_folder_pt2}'
    str_season = format_season_episode_num(season)
    if out_location != "":
        import os
        if os.name == 'nt':
            f_sep = "\\"
        else:
            f_sep = "/"
        if title != "" and out_location != folder:
            out_location_full = f"{out_location}{f_sep}{title} - S{str_season}"
            Path(out_location_full).mkdir(parents=True, exist_ok=True)
        else:
           out_location_full = folder
    else:
       out_location_full = folder


    #episode file naming
    reset_special = special
    reset_episode = episode
    str_playall = ""
    dict_prompt = {}
    for i in range(0, 2):
        if i == 1:
           special = reset_special
           episode = reset_episode
           answer = query_yes_no("Proceed with rename?")
           if answer == False:
              break
        bool_episode_pair = False
        if bool_mtime == True:
           os_list = list(filter(os.path.isfile, glob.glob(folder + "\\*")))
           os_list.sort(key=lambda x: os.path.getmtime(x))
           os_list = map(os.path.basename, os_list)
        else:
           os_list = os.listdir(folder)
        if bool_reverse == True:
           os_list = reversed(os_list)

        
        for filename in os_list:
          file_location = os.path.join(folder, filename)
          
          if bool_ffmpeg: #time length calculations
             time_length = dict_time[file_location] #filepath:timeobject
             int_t_len = datetime.timedelta(hours=time_length.tm_hour,minutes=time_length.tm_min,seconds=time_length.tm_sec).total_seconds()
             int_t_clip = datetime.timedelta(hours=extras_clip_time.tm_hour,minutes=extras_clip_time.tm_min,seconds=extras_clip_time.tm_sec).total_seconds()
             out_time = strftime("%H:%M:%S", time_length )
             if i == 0 and bool_verbose:
                print(f"Length: {out_time}   Seconds diff: {get_time_diff(time_length, extras_clip_time)}")
             if bool_force_all == True:
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                bool_special = False
             elif bool_detect_e_count == True and round (int_t_len /int_t_clip) > 1:
                int_e_count = round (int_t_len /int_t_clip) -1 #auto-correct
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                bool_episode_pair = True
                bool_special = False
             elif get_diff(int_t_len, int_t_clip *2) < clipping_time_variance:
                print("two part episode")
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                int_e_count = 1
                bool_episode_pair = True
                bool_special = False
             elif episode ==1 and int_t_len > int_t_clip and season == 1: #Episode 1 can be longer for season 01
                if i == 1:
                   print("Long first episode detected")
                   #I want to decrease the episode length if an average (autodetect) was used.
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                bool_special = False
                #need to adjust clip extras_clip_time and clipping_time_variance if we used prevalence

             elif get_time_diff(time_length, extras_clip_time) > clipping_time_variance:
                 if get_time_diff(time_length, extras_clip_time) < clipping_time_variance *2:
                    if time_length in dict_prompt: #only prompt once
                        is_episode = dict_prompt[time_length]
                    else:    
                        is_episode = query_yes_no(f'File length is {time_length.tm_hour}:{time_length.tm_min}:{time_length.tm_sec}. Is this an episode?')
                    if is_episode: 
                        string_episode = f'{episode}'
                        str_season = format_season_episode_num(season)
                        bool_special = False
                        dict_prompt[time_length] = True
                    else:
                        string_episode = f'{special}'
                        str_season = format_season_episode_num(0)
                        bool_special = True
                        dict_prompt[time_length] = False
                 else:
                    string_episode = f'{special}'
                    str_season = format_season_episode_num(0)
                    bool_special = True
             else:
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                bool_special = False
          else: #episode detect off size
         
            size = os.path.getsize(file_location)
            if bool_multi_episode_detect == True and size ==multi_episode:
                string_episode = f'{reset_episode}'
                str_season = format_season_episode_num(season)
            elif size < extras_clipping_size and not (extras_clipping_size - size < clipping_variance) or bool_low_prev_special== True and dict_size_prev[size] == 1:
                string_episode = f'{special}'
                str_season = format_season_episode_num(0)
                bool_special = True
            else:
                string_episode = f'{episode}'
                str_season = format_season_episode_num(season)
                bool_special = False
          if len(string_episode) == 1:
            string_episode = f"0{string_episode}"
          if bool_episode_pair == True:
            bool_playall = is_play_all(time_length, list_size, list_time, string_episode, episode + int_e_count) #is this roughly the other episodes combined?
            if bool_playall == True:
               str_playall = file_location
               print(f'Play all episode detected and set to skip - {file_location}')
               int_e_count = 0
               bool_episode_pair = False
               continue
            else:
                episode = episode + int_e_count
                bool_episode_pair = False

                if len(str(episode)) == 1:
                    string_episode = f"{string_episode}-e0{episode}"
                else:
                    string_episode = f"{string_episode}-e{episode}"
          if bool_title_filename == True and title != "":
            title_string = f"{title} - "
          else:
            title_string = ""
        
          if bool_multi_episode_detect == True and size ==multi_episode:
             string_episode = string_episode + "-TBD"
          if i ==0:
             print (f"{filename}={title_string}S{str_season}e{string_episode}.mkv")
          elif i == 1 and str_playall != file_location:
            os.rename(folder +"\\" + filename, out_location_full +"\\" + f"{title_string}S{str_season}e{string_episode}.mkv")
          if bool_multi_episode_detect == True and size ==multi_episode:
            print("multi-episode file detected. Will rename after identifying last episode number")
          elif bool_special == True:
            special +=1
          else:
            episode = episode +1
        if i == 1 and bool_multi_episode_detect == True and multi_episode > 0:
            os.rename(folder +"\\" + f"{title_string}S{str_season}e{reset_episode}-TBD.mkv", folder +"\\" + f"{title_string}S{str_season}e{reset_episode}-e{string_episode}.mkv")
    if answer and bool_continue == True:
      logToFile("config.ini", "[season_rename]", True, "w")
      logToFile("config.ini", f"title={title}", False, "a")
      logToFile("config.ini", f"season={season}", False, "a")
      logToFile("config.ini", f"episode={episode}", False, "a")
      logToFile("config.ini", f"special={special}", False, "a")
      logToFile("config.ini", f"bool_bluray={bool_bluray}", False, "a")
      logToFile("config.ini", f"dir={dir_name}", False, "a")

    if answer:
       print(f"Files renamed to folder path \"{out_location_full}\"")
       arg_folder = ""
       if opts.outlocation:
           arg_folder = opts.outlocation


       import subprocess

       import sys

       if folder != next_folder and os.path.exists(next_folder ): #prompt for next disc
           arg_directory = f'-d "{next_folder}" '
           arg_season = f'-s {season} '
       
       
           answer = query_yes_no("Proceed to next disc?")
           if answer:
            episode_rename(next_folder, season,extras_clipping_size, extras_clip_time,clipping_time_variance,title,episode,special,arg_folder)
       elif os.path.exists(next_season_folder):

           answer = query_yes_no("Proceed to next season?")
           if answer:
               episode_rename(next_season_folder, season +1,extras_clipping_size, extras_clip_time, clipping_time_variance,title,1,special,arg_folder)

    else:
       print("rename skipped")

episode_rename(folder, season,extras_clipping_size, extras_clip_time, clipping_time_variance,title,episode,special, out_location)
