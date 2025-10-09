#!/bin/bash
# Direct FFmpeg command test to verify the approach works

set -e

# Create temp directory
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "Creating test files in $TMPDIR..."

# Create 2-second audio
ffmpeg -f lavfi -i anullsrc=r=44100:cl=mono -t 2.0 -y "$TMPDIR/audio.wav" 2>&1 | tail -3

# Create test PNG background
ffmpeg -f lavfi -i color=c=blue:size=1920x1080 -frames:v 1 -y "$TMPDIR/bg.png" 2>&1 | tail -3

# Create subtitle
cat > "$TMPDIR/subtitle.srt" <<EOF
1
00:00:00,000 --> 00:00:02,000
Test subtitle
EOF

echo "Testing video generation with looped PNG..."

# Test the command with loop (no timeout for 2-second video)
ffmpeg \
  -loop 1 -t 2.0 -r 30 -i "$TMPDIR/bg.png" \
  -i "$TMPDIR/audio.wav" \
  -filter_complex "[0:v]scale=2266:1274,zoompan=z='if(eq(on,0),1.0,min(1.12,zoom+0.00035))':s=1920x1080:fps=30:d=1:x='iw/2-(iw/zoom/2)+sin(on/120)*100':y='ih/2-(ih/zoom/2)+cos(on/150)*80',eq=saturation=1.05:contrast=1.02:brightness=0.01,setsar=1,subtitles='$TMPDIR/subtitle.srt':force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BackColour=&HE0000000,BorderStyle=4,Outline=3,Shadow=3,Alignment=2,MarginV=50,MarginL=100,MarginR=100,Bold=1,Spacing=1,ScaleX=100,ScaleY=100'[v]" \
  -map "[v]" -map 1:a \
  -c:v libx264 -preset slow -crf 20 -b:v 5000k \
  -c:a aac -b:a 128k -ar 44100 \
  -pix_fmt yuv420p -movflags +faststart \
  -y "$TMPDIR/output.mp4" 2>&1 | tail -10

if [ -f "$TMPDIR/output.mp4" ]; then
    echo "✓ Video created successfully!"
    echo "Checking video properties..."
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$TMPDIR/output.mp4"
    ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets -of csv=p=0 "$TMPDIR/output.mp4"
else
    echo "✗ Video creation failed!"
    exit 1
fi
