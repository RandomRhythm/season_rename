# season_rename
Rename television season episodes and extras organized by disc (folders)

## Requirements
* Python3
* ffmpeg
* ffmpeg-python

## Arguments
```
Options:
  -h, --help            show this help message and exit
  -d FOLDER, --directory=FOLDER
                        Folder path to directory containing episodes
  -l EPISODE_LEN, --length=EPISODE_LEN
                        Roughly how long are episodes. Takes format HH:MM:SS
  -n, --new             New show (not continuing the previous one)
  -o OUTLOCATION, --out=OUTLOCATION
                        Output location
  -t TITLE, --title=TITLE
                        Title the episode with this string
  -s SEASON, --season=SEASON
                        Season number
  -v VARIANCE, --variance=VARIANCE
                        Largest variance in seconds between episode lengths
```

## Details
A useful feature is the output argument. Specifying it will create a season subfolder and move the episodes into it. 
```
-o "C:\television"
```

So if you give it a directory path of A_SHOW_YOU_WATCH_S1D1 with the above argument your epsidoes will be moved to:
```
c:\Television\A_SHOW_YOU_WATCH - S01
```

Example:
![Animation](https://github.com/user-attachments/assets/2aef3c01-b768-4568-9aaa-067cf414c8f5)

The above actions created the following structure under the ```'c:\Television'``` output folder:
```
THAT_TV_SHOW - S01
- > THAT_TV_SHOW - S00e01.mkv
- > THAT_TV_SHOW - S01e01.mkv
- > THAT_TV_SHOW - S01e02.mkv
- > THAT_TV_SHOW - S01e03.mkv
- > THAT_TV_SHOW - S01e04.mkv
- > THAT_TV_SHOW - S01e05.mkv
- > THAT_TV_SHOW - S01e06.mkv
- > THAT_TV_SHOW - S01e07.mkv
- > THAT_TV_SHOW - S01e08.mkv
- > THAT_TV_SHOW - S01e09.mkv
- > THAT_TV_SHOW - S01e10.mkv
- > THAT_TV_SHOW - S01e11.mkv
- > THAT_TV_SHOW - S01e12.mkv
- > THAT_TV_SHOW - S01e13.mkv
THAT_TV_SHOW - S02
- > THAT_TV_SHOW - S00e02.mkv
- > THAT_TV_SHOW - S00e03.mkv
- > THAT_TV_SHOW - S02e01.mkv
- > THAT_TV_SHOW - S02e02.mkv
- > THAT_TV_SHOW - S02e03.mkv
- > THAT_TV_SHOW - S02e04.mkv
- > THAT_TV_SHOW - S02e05.mkv
- > THAT_TV_SHOW - S02e06.mkv
- > THAT_TV_SHOW - S02e07.mkv
```

Specify the length will help ensure episodes are properly identified. This is an optional argument as the code will attempt to identify episodes automatically. This is particually needed for multi-epsisode files. The following argument tells the script episodes are roughly 24 minutes each:
```
-l "24:00"
```
