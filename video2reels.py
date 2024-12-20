import whisper
import ffmpeg
from textblob import TextBlob
import os
import streamlit as st
import openai
import re
from dotenv import load_dotenv

#Set up OpenAI API Key
load_dotenv()  # Load variables from .env
openai.api_key=os.getenv('openai.api_key')

# Step 1: Extract Audio from Video using FFmpeg
def extract_audio(video_path, output_audio_path):
    try:
        ffmpeg.input(video_path).output(output_audio_path).run()
        print(f"Audio extracted successfully to {output_audio_path}")
    except Exception as e:
        print(f"Error extracting audio: {e}")

# Step 2: Transcribe Audio to Text using OpenAI Whisper
def transcribe_audio(audio_path):
    model = whisper.load_model("base")
    result = model.transcribe(audio_path)
   
# Create output text file name based on the audio file name
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_file = f"{base_name}.txt"

    # Save the extracted text to a text file
    with open(output_file, 'w') as file:
        file.write(result['text'])

    return result['text'], result['segments']

# Function to extract numerical sentiment score from content
def extract_sentiment_score(content):
    match = re.search(r"Sentiment score:\s*([-]?\d+(\.\d+)?)", content)
    if match:
        return float(match.group(1))
    else:
        raise ValueError("Sentiment score not found in the content")

# Function to convert sentiment string to numerical score
def sentiment_to_score(sentiment_content):
    if "positive" in sentiment_content.lower():
        return 1.0
    elif "negative" in sentiment_content.lower():
        return -1.0
    elif "mixed" in sentiment_content.lower():
        return 0.0
    return 0.0


# Step 3: Analyze Text Segments for Importance

def analyze_text_importance(segments):
    important_segments = []
    buffer_time = 0.5  # Buffer to adjust start/end times for smoother cuts

    for segment in segments:
        text = segment['text']
        start_time = max(0, segment['start'] - buffer_time)  # Adding buffer
        end_time = segment['end'] + buffer_time

        # Define prompt for sentiment analysis
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes sentiment."},
                {"role": "user", "content": f"Analyze the sentiment of this text: {text}"}
            ]
        )

        sentiment_analysis = response['choices'][0]['message']['content']
        
        # Determine sentiment score based on response
        sentiment_score = 0
        if "positive" in sentiment_analysis.lower():
            sentiment_score = 1
        elif "negative" in sentiment_analysis.lower():
            sentiment_score = -1

        word_count = len(text.split())
        importance_score = sentiment_score * word_count  # Score based on sentiment and length
        with open("important_segments.txt", "w") as file:
        # Ensure segment ends with punctuation to complete the sentence
            if text and text[-1] in [".", "!", "?"] and importance_score > 1.0:  # Adjust threshold
                important_segments.append({
                    'text': text,
                    'start_time': start_time,
                    'end_time': end_time,
                    'importance_score': importance_score
                })
                
            for segment in important_segments:
                file.write(f"Text: {segment['text']}\n")
                file.write(f"Start Time: {segment['start_time']}s\n")
                file.write(f"End Time: {segment['end_time']}s\n")
                file.write(f"Importance Score: {segment['importance_score']}\n")
                file.write("="*40 + "\n")  # Separator for readability

    return important_segments

# Step 4: Extract Video Segments Based on Timestamps
def extract_video_segment(video_path, start_time, end_time, output_path):
    try:
        duration = end_time - start_time
        ffmpeg.input(video_path, ss=start_time, t=duration).output(output_path).run()
        print(f"Segment extracted: {output_path}")
    except Exception as e:
        print(f"Error extracting video segment: {e}")

# Step 5: Compile Extracted Segments into 30-Second Reel
def compile_video_segments(segment_paths, output_video_path):
    with open('file_list.txt', 'w') as f:
        for segment in segment_paths:
            f.write(f"file '{segment}'\n")

    try:
        ffmpeg.input('file_list.txt', format='concat', safe=0).output(output_video_path, c='copy').run()
        print(f"Compiled reel created: {output_video_path}")
    except Exception as e:
        print(f"Error compiling videos: {e}")

# Step 6: Save timestamps to a text file
def save_timestamps_to_file(segments, output_file):
    with open(output_file, 'w') as f:
        for segment in segments:
            f.write(f"Start: {segment['start_time']:.2f}, End: {segment['end_time']:.2f}\n")
    print(f"Timestamps saved to {output_file}")
def add_subtitle(video_path, text):
    # Temporary subtitle file creation
    caption_file = "temp_captions.srt"

    # You can set the start and end time for the caption here
    start_time = "00:00:00,000"  # example start time
    end_time = "00:00:07,000"  # example end time

    # Write caption details into the SRT file
    with open(caption_file, 'w') as f:
        f.write(f"1\n")
        f.write(f"{start_time} --> {end_time}\n")
        f.write(f"{text}\n")

    # Overlay captions on video segment using ffmpeg
    output_with_captions = video_path.replace('.mp4', '_with_captions.mp4')
    ffmpeg.input(video_path).output(output_with_captions, vf=f"subtitles={caption_file}").run()

    # Clean up the temporary caption file
    os.remove(caption_file)

    # Delete the original video file before renaming
    os.remove(video_path)
    os.rename(output_with_captions, video_path)  # Replace original with captioned version

    
# Full Process: Text Analysis, Timestamp Mapping, Video Extraction, Compilation
def generate_reel_from_important_segments(video_path, audio_path, top_n=5):
    # First, extract audio and perform transcription (existing steps)
    extract_audio(video_path, audio_path)
    _, segments = transcribe_audio(audio_path)  # Generates important_segments.txt with text and timestamps

    print("Transcription and timestamp extraction completed.")
    important_segments = analyze_text_importance(segments)
    important_segments.sort(key=lambda x: x['importance_score'], reverse=True)

    compiled_video_paths = []  # To store the paths of compiled reels

    for reel_index in range(3):
        top_segments = important_segments[reel_index * top_n:(reel_index + 1) * top_n]
        top_segments.sort(key=lambda x: x['start_time'])

        segment_paths = []
        for i, segment in enumerate(top_segments):
            start_time = segment['start_time']
            end_time = segment['end_time']
            text = segment['text']  # Text from the stored important segments

            # Define output path for each segment
            output_path = f'reel_{reel_index + 1}_segment_{i + 1}.mp4'

            # Extract the segment and overlay subtitle
            extract_video_segment(video_path, start_time, end_time, output_path)
            add_subtitle(output_path, text)  # Add text as a subtitle overlay

            segment_paths.append(output_path)

        # Compile all segments for this reel into one video
        compiled_video_path = f'reel_{reel_index + 1}.mp4'
        compile_video_segments(segment_paths, compiled_video_path)
        compiled_video_paths.append(compiled_video_path)

    return compiled_video_paths

# Streamlit Interface
def main():
    st.title("Video to Reel Conveter")

    # Video upload
    uploaded_file = st.file_uploader("Upload a video", type=["mp4"])

    if uploaded_file is not None:
        video_path = f"uploaded_video.mp4"
        with open(video_path, mode="wb") as f:
            f.write(uploaded_file.read())
        st.success("Video uploaded successfully!")

        # Process the video
        if st.button("Generate Reel"):
            audio_path = "extracted_audio.wav"
            compiled_video_path = "compiled_reel.mp4"
            timestamps_file_path = "timestamps.txt"

            st.info("Processing the video...")

            # Generate reel from important segments
            important_segments, segment_paths = generate_reel_from_important_segments(video_path, audio_path, compiled_video_path)

            st.success(f"Reel generated and timestamps saved to {timestamps_file_path}!")

            # Display download link for compiled reel
            with open(compiled_video_path, "rb") as file:
                st.download_button(label="Download Reel", data=file, file_name="compiled_reel.mp4")

            # Provide download link for the timestamps file
            with open(timestamps_file_path, "rb") as file:
                st.download_button(label="Download Timestamps", data=file, file_name="timestamps.txt")

            # Delete segment files after compilation
            for segment_path in segment_paths:
                if os.path.exists(segment_path):
                    os.remove(segment_path)

if __name__ == '__main__':
    main()