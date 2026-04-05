import fitz  # PyMuPDF
import logging
from docx import Document
from groq import Groq
import base64
import os


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s : %(message)s"
)

logger = logging.getLogger("GroqSTTBot")

def read_documents(documents):
    """
    Receives a list of chainlit file types, filters and opens them based on their extension
    Returns text containing all file names along with their contents
    """
    text = ""
    
    for document in documents:
        try:
            if document.path.endswith('.pdf'):
                doc = fitz.open(document.path)
                text += f"\n\n=== File: {document.name} ===\n\n"
                for page in doc:
                    text += page.get_text()
                logger.info(f"Extracted {len(text)} characters from {document.name}")
            
            elif document.path.endswith('.docx'):
                doc = Document(document.path)
                text += f"\n\n=== File: {document.name} ===\n\n"
                text += "\n".join([para.text for para in doc.paragraphs])
                logger.info(f"Extracted DOCX content from {document.name}")
            
            elif document.path.endswith('.txt'):
                with open(document.path, "r", encoding='utf-8') as f:
                    text += f"\n\n=== File: {document.name} ===\n\n"
                    text += f.read()
                logger.info(f"Extracted TXT content from {document.name}")
            
            elif document.path.endswith(('.png', '.jpg', '.jpeg', "webp")):
                base64_image = encode_image(document.path)

                client = Groq(api_key = os.environ.get("GROQ_API_KEY"))

                ext = document.path.rsplit('.', 1)[-1].lower()
                mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

                chat_completion = client.chat.completions.create(
                    messages = [
                        {
                            "role":"user",
                            "content":[
                                {"type": "text", "text": "Describe the content of this in details."},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime};base64,{base64_image}"
                                    },
                                },
                            ],
                        }
                    ],
                    model = "meta-llama/llama-4-scout-17b-16e-instruct"
                )
                
                text += f"\n\n=== File: {document.name} ===\n\n"
                text += chat_completion.choices[0].message.content
                logger.info(f"Extracted image description from {document.name}")

            else:
                logger.warning(f"Unsupported file type: {document.name}")
        
        except Exception as e:
            logger.error(f"Error reading {document.name}: {e}", exc_info=True)
            text += f"\n\n⚠️ Could not read {document.name}: {str(e)}\n\n"
    
    return text

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    
if __name__ == "__main__":
    logger.info("cannot import this module")
