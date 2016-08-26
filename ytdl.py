#!/usr/bin/python

import sys
import os
import codecs
import time
import http.client
import urllib.parse

import execjs

from apiclient.discovery import build
from apiclient.errors import HttpError
from oauth2client.tools import argparser


# Set DEVELOPER_KEY to the API key value from the APIs & auth > Registered apps
# tab of
#   https://cloud.google.com/console
# Please ensure that you have enabled the YouTube Data API for your project.
DEVELOPER_KEY = "your_api_key_here"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

dir = ""

requestheaders={"Connection":"keep-alive",
	"Accept":"*/*",
	"Referer":"http://www.youtube-mp3.org/",
	"Cache-Control":"no-cache",
	"Accept-Location":"*",
	"Accept-Language":"en-US,en;q=0.8",
	"User-Agent":"Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/52.0.2743.116 Safari/537.36"}

def youtube_search(options, query=None, max_results=None):
  youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,
    developerKey=DEVELOPER_KEY)

  # Call the search.list method to retrieve results matching the specified
  # query term.
  search_response = youtube.search().list(
    q=(options.query if query == None else query),
    part="id,snippet",
    maxResults=(options.max_results if max_results == None else max_results)
  ).execute()

  videos = []
  print("Query = %s" % (options.query if query == None else query))
  print("Executing youtube search query...")
  # Add each result to the appropriate list, and then display the lists of
  # matching videos, channels, and playlists.
  for search_result in search_response.get("items", []):
    if search_result["id"]["kind"] == "youtube#video":
      videos.append(search_result)
  
  
  print("Done")
  
  return videos
  #print "Channels:\n", "\n".join(channels), "\n"
  #print "Playlists:\n", "\n".join(playlists), "\n"

# Converts the video respresented by the given ID and writes it to a file in the working directory
def convert_video(id, options):
  # Open and compile Javascript file containing functions from the client script of youtube-mp3.org
  js = open("ytdlhelper.js")
  compiledjs = execjs.compile(js.read())
  js.close()
  pushurl = compiledjs.call("get_push_url", id)
  infourl = compiledjs.call("get_info_url", id)
  print("Pushing request to convert video with ID \"%s\"" % id);
  conn = http.client.HTTPConnection("www.youtube-mp3.org", 80)
  print("Pushing conversion request to server...")
  conn.request("GET", pushurl, headers=requestheaders)
  resp = conn.getresponse()
  print("Status: %s %s" % (resp.status, resp.reason))
  if resp.status != 200:
    print("Error: Unexpected behavior was detected from the server.")
    return
  conn = http.client.HTTPConnection("www.youtube-mp3.org", 80)
  print("Retrieving item info...")
  conn.request("GET", infourl, headers=requestheaders)
  resp = conn.getresponse()
  print("Status: %s %s" % (resp.status, resp.reason))
  if resp.status != 200:
    print("Error: Unexpected behavior was detected from the server.")
    return
  print("Parsing info object...")
  jsonstring = resp.read().decode(sys.stdout.encoding)
  startindex = 0
  for i in range(0, len(jsonstring)):
    if jsonstring[i] == '{':
      startindex=i
      break  
  jsonstring = jsonstring[i:len(jsonstring)-1]
  geturl = compiledjs.call("get_file_url", id, jsonstring)
  conn = http.client.HTTPConnection("www.youtube-mp3.org", 80)
  print("Retrieving MP3 file...")
  conn.request("GET", geturl, headers=requestheaders)
  resp = conn.getresponse()
  print("Status: %s %s" % (resp.status, resp.reason))
  if resp.status != 302:
    print("Error: Unexpected behavior was detected from the server.")
    return
  mp3url = urllib.parse.urlparse(resp.getheader("Location"))
  print("Retrieving file from %s" % mp3url.hostname)
  conn = http.client.HTTPConnection(mp3url.hostname, 80)
  conn.request("GET", mp3url.geturl(), headers=requestheaders)
  resp = conn.getresponse()
  print("Status: %s %s" % (resp.status, resp.reason))
  if resp.status != 200:
    print("Error: Unexpected behavior was detected from the server.")
    return
  content_disposition = resp.getheader("Content-Disposition")
  filename = "%sdefault.mp3" % dir
  try:
    filename = "%s%s" % (dir, content_disposition.split(';')[1].split('=')[1].strip('"'))
  except Exception:
    print("Error: Bad response: Content-Disposition header not present or not in expected format.")
  if resp.getheader("Content-Type") != "application/octet-stream":
    print("Error: Server sent data in an unexpected format")
    return
  print("Writing to file \"%s%s\"" % (dir, filename.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)))
  outfile = open(filename, "wb")
  outfile.write(resp.read())
  print("Done")
    

if __name__ == "__main__":
  argparser.add_argument("-q", "--query", help="Search term", default="Google")
  argparser.add_argument("--max-results", help="Max results", type=int, default=25)
  argparser.add_argument("-a", "--auto", help="Automatically selects the first result of the query, instead of asking the user to input a choice", action='store_true')
  argparser.add_argument("--batch", help="Batch downloads videos in the file specified", metavar="FILE", default=None)
  argparser.add_argument("-s", "--quiet", "--silent", help="Output nothing", action='store_true')
  argparser.add_argument("dir", help="Specifies destination directory", default=".")
  argparser.add_argument("-v", "--verbose", action='store_true', help="More detailed output")
  argparser.add_argument("-h", "--help", help="Prints this message", action='help')
  argparser.add_argument("--query-only", help="Only perform the YouTube search, do not download mp3", action='store_true')
  argparser.add_argument("--id", help="Download video represented by the specified id", default=None)
  args = argparser.parse_args()
  
  if args.dir != ".":
    if not os.path.isdir(args.dir):
      os.makedirs(args.dir)
    dir = "%s%s" % (args.dir, "\\")

  batch = []
  batch.append(args.query)
  
  if args.batch != None:
    batchfile = None
    try:
      batchfile = open(args.batch, "r")
    except IOError:
      print("Error: File \"%s\" does not exist" % args.batch)
      exit()
    batch = batchfile.read().split('\n')
      
  for query in batch:
    results = youtube_search(args, query=query)
    videos = []
    if args.auto == False or args.verbose == True:
      for i in range(0, len(results)):
        videos.append("%s) %s (%s)" % (str(i), results[i]["snippet"]["title"], results[i]["id"]["videoId"]))
        videos[i] = videos[i].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding)
    
      print("Results:\n", "\n".join(videos), "\n")
    
    selection = 0
    if args.auto == False:
      while True:
        try:
          selection = int(input("Input the number of your selection: "))
        except ValueError:
          print("You did not enter a valid integer")
        else:
          if selection < 0 and selection >= len(results):
            print("Your selection is out of range")
            continue
          break
      
    if args.query_only == False:
      convert_video(results[selection]["id"]["videoId"], args)
  
  
