import google.generativeai as genai

def test_gemini_api_key(api_key):
    try:
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel('gemini-1.5-pro')
        prompt = "Write a short story about a robot who learns to love. The story should be no more than 100 words."
        response = model.generate_content(prompt)
        print("API key is working.")
        print("Response:", response.text)
        return True

    except Exception as e:
        print("API key is NOT working:", e)
        return False

# Replace 'YOUR_GEMINI_API_KEY' with your actual API key
api_key = "AIzaSyAmnNB-HuMLCI1z6kqzSEDeeLwKZMOMwtY"

test_gemini_api_key(api_key)