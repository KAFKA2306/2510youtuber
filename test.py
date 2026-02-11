import ffmpeg
import os
try:
    (
        ffmpeg
        .input('color=c=black:s=1280x720:r=25', f='lavfi', t=5)
        .output('test.mp4')
        .run(cmd="ffmpeg", overwrite_output=True, capture_stdout=True, capture_stderr=True)
    )
    print("ffmpeg command executed successfully.")
    if os.path.exists("test.mp4"):
        print("test.mp4 created.")
except ffmpeg.Error as e:
    print("ffmpeg command failed.")
    print("stdout:", e.stdout.decode('utf8'))
    print("stderr:", e.stderr.decode('utf8'))
