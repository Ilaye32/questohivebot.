import fitz  # PyMuPDF
import logging
from docx import Document  # This will now work correctly

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
            
            else:
                logger.warning(f"Unsupported file type: {document.name}")
        
        except Exception as e:
            logger.error(f"Error reading {document.name}: {e}", exc_info=True)
            text += f"\n\n⚠️ Could not read {document.name}: {str(e)}\n\n"
    
    return text
