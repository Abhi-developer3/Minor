# multimodal.py
import os,time
import requests
from io import BytesIO
from PIL import Image
import base64
from dotenv import load_dotenv
import streamlit as st
import google.generativeai as genai
from google.cloud import vision
from huggingface_hub import InferenceClient
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import fal_client


load_dotenv()
HF_TOKEN = os.getenv("HF_TOKEN")
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 1. Text to Image
def text_to_image(prompt: str, width: int = 1024, height: int = 1024) -> Image.Image:
    API_URL = "https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell"
    payload = {
        "inputs": prompt,
        "parameters": {
            "width": width,
            "height": height,
            "num_inference_steps": 28,  
            "guidance_scale": 7.5
        }
    }
    resp = requests.post(API_URL, headers=HF_HEADERS, json=payload, timeout=120)  
    if resp.status_code == 503:  # Model loading – common on first run
        st.warning("Model is warming up... Please wait 1-2 minutes and try again.")
        raise Exception("Model not ready yet")
    resp.raise_for_status()
    image_bytes = resp.content
    if not image_bytes or len(image_bytes) < 100:
        raise Exception("Empty response from API")
    return Image.open(BytesIO(image_bytes))


# 2. Image to Text (Caption)
processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")

def image_to_text(img: Image.Image) -> str:
    try:
        inputs = processor(img, return_tensors="pt")
        out = model.generate(**inputs, max_new_tokens=20)
        caption = processor.decode(out[0], skip_special_tokens=True)
        words = caption.split()
        return " ".join(words[:]).strip()
    except:
        return "Caption failed."

# Helper: PIL to base64
def pil_to_b64(img: Image.Image) -> str:
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
