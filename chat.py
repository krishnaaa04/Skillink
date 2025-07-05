import os
import logging
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from flask import jsonify

# Configure Gemini API
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def handle_chat_request(user_message):
    if not user_message:
        logging.error("Message cannot be empty")
        return jsonify({"response": "Please enter a message."}), 400

    try:
        logging.debug(f"User message: {user_message}")

        system_instruction = """You are Skillink Assistant, the official AI helper for the Skillink platform. 
        Your role is to:
        - Help users understand Skillink's features
        - Guide them through signup/login processes
        - Explain how to use employee/employer dashboards
        - Provide general career advice when appropriate
        - Be polite, professional and concise
        - Only answer questions related to Skillink or general career topics
        - For unrelated questions, politely decline to answer
        
        Current Skillink Features:
        - Employee profile management
        - Certificate tracking
        - Job search tools
        - Interview scheduling
        - Skills assessment
        
        Always respond in a helpful but brief manner (2-3 sentences max)."""

        generation_config = {
            "temperature": 0.7,
            "top_p": 0.9,
            "top_k": 40,
            "max_output_tokens": 1024,
        }

        safety_settings = [
            {"category": HarmCategory.HARM_CATEGORY_HARASSMENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
            {"category": HarmCategory.HARM_CATEGORY_HATE_SPEECH, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
            {"category": HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
            {"category": HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, "threshold": HarmBlockThreshold.BLOCK_ONLY_HIGH},
        ]

        model = genai.GenerativeModel(
            model_name="models/gemini-1.5-pro-latest",
            generation_config=generation_config,
            safety_settings=safety_settings
        )

        logging.debug("Sending message to Gemini API...")
        chat = model.start_chat(history=[], system_instruction=system_instruction)
        response = chat.send_message(user_message)
        logging.debug("Gemini API response received.")

        response_text = response.text

        logging.debug(f"AI Response: {response_text}")

        return jsonify({"response": response_text})

    except Exception as e:
        logging.error(f"Gemini API Error: {str(e)}")
        return jsonify({"response": "I'm experiencing technical difficulties. Please try again later."}), 500