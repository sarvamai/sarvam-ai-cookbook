# 📚 PDF Q&A with Sarvam AI
A powerful Streamlit application that enables natural language question-answering over PDF documents using Sarvam AI's advanced language model and LlamaIndex for intelligent document processing.
## 🚀 Features
- **PDF Document Upload**: Upload multiple PDF files for processing
- **Intelligent Q&A**: Ask natural language questions about your document content
- **Sarvam AI Integration**: Leverages Sarvam-M model for accurate responses
- **Vector Search Index**: Fast and efficient document retrieval using embeddings
- **Source Referencing**: View source snippets for answer verification
- **Configurable Parameters**: Customize chunk sizes, model settings, and behavior
- **API Connection Testing**: Verify your Sarvam AI API credentials before processing

For Demo: [Demo](https://sarvam-pdf-bot.streamlit.app/)
## 📋 Requirements
### Python Packages
```bash
pip install -r requirements.txt
```
### API Requirements
- Sarvam AI API Key: Get From [Sarvam Dashboard](https://dashboard.sarvam.ai/key-management)
(Free tier includes 1000 credits & Sign up to get your API key)


## Installation
### Cloning
```bash
git clone https://github.com/PredictiveManish/Q-A-with-sarvam.git
(or fork and then https://github.com/<your-username>/Q-A-with-sarvam)

cd pdf-qa-sarvam
```
### Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
# or install manually:
pip install streamlit llama-index fastembed requests
```

### Setup & Configuration
1. Get Sarvam AI API Key

- Visit Sarvam AI Dashboard
- Create an account or sign in
- Navigate to API Key Management
- Generate a new API key
- Copy your API key
- Configure the Application

Run the Streamlit application:
```bash
streamlit run app.py
```
- Enter your Sarvam AI API key in the sidebar
- Optional: Test API connection using the "Test API Connection" button

## 📖 Usage

### Step 1: Upload Documents
- Click on **"Choose PDF files"** in the sidebar  
- Select one or more PDF documents  
- Wait for processing to complete  

### Step 2: Ask Questions
- Navigate to the **"Ask Questions"** section  
- Type your natural language question  
- Click **"Get Answer"** to receive a response  
- Expand **"View Sources"** to see reference snippets  

### Step 3: Configure Settings
Use the sidebar to adjust:

- **Context Window Size**: Memory allocation (1024–8192 tokens)  
- **Max Response Tokens**: Length of responses (64–2048 tokens)  
- **Chunk Size**: Document segmentation (256–4096 tokens)  
- **Temperature**: Response randomness (0.0–1.0)  
- **Top K Retrieval**: Number of sources to use (1–10)  
- **System Prompt**: Custom assistant behavior  

---

## 🛠️ Configuration Options

### Model Settings
- **Model**: Sarvam-M (configurable via API)  
- **Context Window**: Default 4500 tokens  
- **Chunk Overlap**: 200 tokens for context preservation  

### Processing Parameters
- **Chunk Size**: Controls document segmentation  
- **Embedding Model**: BAAI/bge-small-en-v1.5  
- **Similarity Top K**: Number of documents retrieved per query  

---

## 🔧 Advanced Features

### System Prompt Customization
Modify the assistant behavior by editing the **System Prompt** field:

```text
You are a helpful Q&A assistant. Answer questions based only on the provided documents. 
If the answer is not in the documents, say "I cannot find this information in the provided documents."
Provide clear, concise answers with relevant details from the documents.

## 🔗 API Testing

Before processing large documents, test your API connection:

- Enter API key and base URL  
- Click **"Test API Connection"**  
- Verify successful connection  

---

## 🐛 Troubleshooting

### Common Issues

#### API Connection Errors
- Verify API key format  
- Check base URL: `https://api.sarvam.ai`  
- Ensure internet connectivity  
- Check API quota/limit  

#### Document Processing Errors
- Ensure PDFs are valid and readable  
- Check file size limits (recommended < 50MB)  
- Verify file permissions  

#### Memory Issues
- Reduce chunk size  
- Decrease context window  
- Close other applications  

#### Empty or Incorrect Answers
- Check system prompt configuration  
- Verify document content quality  
- Adjust temperature and retrieval parameters  

### Debug Mode
Enable detailed error messages by checking browser console for API responses.

---

## 📊 Technical Architecture

### Components
- **Streamlit**: Web framework for UI  
- **LlamaIndex**: Document indexing and retrieval  
- **FastEmbed**: Embedding generation  
- **Sarvam AI API**: Language model inference  
- **Vector Store**: Efficient similarity search  

### Workflow
1. **Upload**: Files → Temporary storage  
2. **Processing**: PDF → Text → Chunks → Embeddings  
3. **Indexing**: Vector store creation  
4. **Querying**: Question → Enhanced prompt → LLM → Answer  

---

## 🔒 Security Notes

- API keys are stored in session state only  
- Temporary files are auto-cleaned  
- No permanent storage of uploaded documents  
- HTTPS API connections only  

---

## 🤝 Contributing

This project is open for enhancements! Please:

- Fork the repository  
- Create a feature branch  
- Submit a pull request  
- Ensure all tests pass  

### Areas for Improvement
- Multi-language support  
- Document format expansion (DOCX, TXT)  
- Advanced question answering  
- Performance optimization  
- User authentication  

---

## 📄 License

This project is licensed under the MIT License — see the `LICENSE` file for details.

---

## 🙏 Acknowledgments

- Sarvam AI for providing the Sarvam-M model  
- LlamaIndex for document intelligence  
- Open source community for tools and libraries  