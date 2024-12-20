import streamlit as st
import os
import uuid
import psycopg2
from io import BytesIO
from PIL import Image
from video2reels import generate_reel_from_important_segments
import re  # For email validation

# Connect to PostgreSQL


conn = psycopg2.connect(
    host=os.getenv("DB_HOST"),
    database=os.getenv("DB_NAME"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    port=os.getenv("DB_PORT")
)
cur = conn.cursor()
def redirect_to_profile():
    st.session_state['page'] = 'Profile'

def delete_reel_segments():
    try:
        # Iterate over possible segment files to delete
        for i in range(1, 4):  # Assuming 3 reels
            for j in range(1, 6):  # Assuming 5 segments per reel
                file_path = f"reel_{i}_segment_{j}.mp4"
                try:
                    os.remove(file_path)
                    print(f"Deleted: {file_path}")
                except FileNotFoundError:
                    print(f"File not found: {file_path}")
                    
        # Delete main reel files if they exist
        for i in range(1, 4):
            try:
                os.remove(f'reel_{i}.mp4')
            except FileNotFoundError:
                print(f"File reel_{i}.mp4 does not exist")

    except Exception as e:
        st.error(f"Error deleting reel segments: {e}")



# Function to verify login credentials from PostgreSQL
def verify_login(email, password):
    try:
        query = "SELECT password FROM users WHERE email = %s"  # Update query to use email
        cur.execute(query, (email,))
        result = cur.fetchone()
        return result and result[0] == password  # Return True if passwords match
    except Exception as e:
        st.error(f"Database error: {e}")
        return False


# Function to create a new user
def create_user(username, password, email, phone_no, dob, profession, gender, profile_pic):
    if not username or not password or not email or not phone_no or gender == "Select":
        st.error("Please fill in all required fields.")
        return False

    # Password validation: Check if it meets strength criteria
    if len(password) < 8 or not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password) or not re.search(r"[0-9]", password) or not re.search(r"[!@#$%^&*()_+=-]", password):
        st.error("Password must be at least 8 characters long, include an uppercase letter, a lowercase letter, a digit, and a special character.")
        return False
     # Check if passwords match


    # Email validation: Check if it contains an @ symbol
    if '@' not in email or not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        st.error("Please enter a valid email address.")
        return False
 # Check for uppercase letters
    if any(char.isupper() for char in email):
        st.error("Email must not contain any capital letters.")
        return False

    # Mobile number validation: Check if it starts with 9, 8, 7, or 6 and is 10 digits long
    if not re.match(r"^[6789]\d{9}$", phone_no):
        st.error("Please enter a valid mobile number starting with 9, 8, 7, or 6 and consisting of 10 digits.")
        return False
    try:
        # Process the profile picture if uploaded
        profile_pic_data = profile_pic.read() if profile_pic else None
        query = "INSERT INTO users (username, password, email, phone_no, dob, profession, gender, profile_pic) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        cur.execute(query, (username, password, email, phone_no, dob, profession, gender, profile_pic_data))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Error creating user: {e}")
        return False


# Function to fetch user details and profile picture
def fetch_user_details(email):
    try:
        query = "SELECT username, email, phone_no, profile_pic FROM users WHERE email = %s"
        cur.execute(query, (email,))
        result = cur.fetchone()
        return result if result else None
    except Exception as e:
        st.error(f"Error fetching user details: {e}")
        return None


# Function to clean up any previous files
def cleanup_files(file_paths):
    for file_path in file_paths:
        if os.path.exists(file_path):
            os.remove(file_path)


# Function to call the reel generation process
def generate_reel(video_file):
    unique_id = str(uuid.uuid4())
    video_path = f'uploaded_video_{unique_id}.mp4'
    audio_path = f'output_audio_{unique_id}.wav'
    compiled_video_path = [f'compiled_reel_{unique_id}_{i}.mp4' for i in range(1,4)]

    with open(video_path, 'wb') as f:
        f.write(video_file.read())

    output_reels=generate_reel_from_important_segments(video_path, audio_path, top_n=5)

    cleanup_files([video_path, audio_path])
    
    return output_reels if all(os.path.exists(path) for path in output_reels) else None
  # Call the function to display the profile

   


# Function to delete a generated reel file after download
def delete_reel(file_path):
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        st.error(f"Error deleting reel: {e}")


# Function to render the profile page
def show_profile():
    user_details = fetch_user_details(st.session_state['email'])
    if user_details:
        username, email, phone_no, profile_pic_data = user_details
        st.subheader("Profile Information")
        st.write(f"*Username*: {username}")
        st.write(f"*Email*: {email}")
        st.write(f"*Phone Number*: {phone_no}")

        if profile_pic_data:
            # Display profile picture
            image = Image.open(BytesIO(profile_pic_data))
            #rotated_image = image.rotate(90, expand=True)
            small_image = image.resize((100, 100))
            st.image(small_image, caption="Profile Picture", use_column_width=False)

        # Logout button
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.session_state['email'] = None
            st.success("Successfully logged out!")
    else:
        st.error("Could not load profile details.")


# Main Streamlit app
st.title("Video-2-Reel-Converter")

# Navigation
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

if 'page' not in st.session_state:
    st.session_state['page'] = 'Home'  # Default to Home page

# If the user is logged in
if st.session_state['logged_in']:
    # Create a sidebar for navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Profile"])

    # Set the selected page in session state
    st.session_state['page'] = page

    

    if st.session_state['page'] == "Home":
        st.subheader(f"Welcome, {st.session_state['email']}!")  # Display email
        delete_reel_segments()

        # Video Upload Section
        uploaded_file = st.file_uploader("Upload a video file", type=["mp4", "mov", "avi"])

        if uploaded_file is not None:
            st.video(uploaded_file)

            if 'reels_generated' not in st.session_state:
                st.session_state['reels_generated'] = False

            if st.button("Generate Reels") and not st.session_state['reels_generated']:
                st.session_state['reels_generated'] = False
                st.write("Processing... This may take a few minutes.")
                with st.spinner(text="In progress..."):
                    output_reels = generate_reel(uploaded_file)  # Call the function to generate reels
                    st.session_state['reels_generated'] = True

                if output_reels:
                    st.session_state['output_reels'] = output_reels
                    st.session_state['reels_generated'] = True
                    st.success("Reels successfully generated!")
                else:
                    st.error("Error generating reels. Please try again.")

            if st.session_state.get('reels_generated', False):
                for idx, output_reel in enumerate(st.session_state['output_reels']):
                    st.video(output_reel)

                    with open(output_reel, 'rb') as f:
                        reel_data = f.read()

                    st.download_button(label=f"Download Reel {idx + 1}", data=reel_data, file_name=f"reel_{idx + 1}.mp4", mime="video/mp4")


    elif st.session_state['page'] == "Profile":
        show_profile()

else:
    # Login/Create Account page
    login_mode = st.radio("Select Option", ("Login", "Create Account"))

    if login_mode == "Login":
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Submit"):
            if verify_login(email, password):
                st.session_state['logged_in'] = True
                st.session_state['email'] = email
                st.success(f"Welcome, {email}!")
            else:
                st.error("Invalid email or password")

    else:  # Create Account
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        email = st.text_input("Email")
        phone_no = st.text_input("Phone Number")
        dob = st.date_input("Date of Birth")
        profession = st.text_input("Profession/Role")
        gender = st.selectbox("Gender", ["Select", "Male", "Female", "Other"])
        profile_pic = st.file_uploader("Upload Profile Picture", type=["jpg", "png"])

        if st.button("Register"):
            if create_user(username, password, email, phone_no, dob, profession, gender, profile_pic):
                st.success("User account created successfully!")