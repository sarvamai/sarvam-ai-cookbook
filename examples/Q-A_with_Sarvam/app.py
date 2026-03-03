import streamlit as st
import os
import tempfile
import requests
import json
from typing import Optional, List, Dict, Any
import time
from pathlib import Path

# Import LlamaIndex components (these are available on PyPI)
try:
    from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings
    from llama_index.core.node_parser import SimpleNodeParser
    from llama_index.core.schema import TextNode
    from llama_index.embeddings.fastembed import FastEmbedEmbedding
    from llama_index.core.embeddings import BaseEmbedding
    from llama_index.core.llms import LLM, CompletionResponse
    from llama_index.core.callbacks import CallbackManager
    from llama_index.core.base.llms.types import LLMMetadata
    import llama_index.core
except ImportError as e:
    st.error(f"Import error: {e}")
    st.info("Please install the required packages from requirements.txt")

# Page configuration
st.set_page_config(
    page_title="PDF Q&A with Sarvam AI",
    page_icon="📚",
    layout="wide"
)

# Custom Sarvam LLM class for LlamaIndex
class SarvamLLM(LLM):
    """Custom LLM class for Sarvam AI API"""
    
    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(
            context_window=4500,
            num_output=512,
            model_name="sarvam-m"
        )
    
    def __init__(self, api_key: str, base_url: str = "https://api.sarvam.ai", **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = "sarvam-m"
    
    def complete(self, prompt: str, **kwargs) -> CompletionResponse:
        """Complete a prompt using Sarvam AI API"""
        try:
            headers = {
                "Content-Type": "application/json",
                "api-subscription-key": self.api_key
            }
            
            # Sarvam AI API payload
            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.1),
                "top_p": kwargs.get("top_p", 0.9),
                "stream": False
            }
            
            # Make API call
            response = requests.post(
                f"{self.base_url}/llm/completion",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                if "generated_text" in result:
                    text = result["generated_text"]
                elif "text" in result:
                    text = result["text"]
                elif "choices" in result and len(result["choices"]) > 0:
                    text = result["choices"][0].get("text", "")
                else:
                    text = str(result)
                
                return CompletionResponse(text=text)
            else:
                error_msg = f"API Error {response.status_code}: {response.text}"
                st.error(error_msg)
                return CompletionResponse(text=f"Error: {error_msg}")
                
        except Exception as e:
            error_msg = f"Error calling Sarvam API: {str(e)}"
            st.error(error_msg)
            return CompletionResponse(text=f"Error: {error_msg}")
    
    def stream_complete(self, prompt: str, **kwargs):
        """Stream completion (not implemented)"""
        raise NotImplementedError("Streaming not implemented for Sarvam LLM")

# Initialize session state
if 'api_key' not in st.session_state:
    st.session_state.api_key = ""
if 'index' not in st.session_state:
    st.session_state.index = None
if 'query_engine' not in st.session_state:
    st.session_state.query_engine = None
if 'uploaded_files' not in st.session_state:
    st.session_state.uploaded_files = []
if 'processing_complete' not in st.session_state:
    st.session_state.processing_complete = False
if 'base_url' not in st.session_state:
    st.session_state.base_url = "https://api.sarvam.ai"

def save_uploaded_files(uploaded_files):
    """Save uploaded files to temporary directory"""
    saved_paths = []
    temp_dir = tempfile.mkdtemp()
    
    for uploaded_file in uploaded_files:
        file_path = os.path.join(temp_dir, uploaded_file.name)
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_path)
    
    return saved_paths, temp_dir

def test_sarvam_api(api_key: str, base_url: str) -> bool:
    """Test if Sarvam API is accessible"""
    try:
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": api_key
        }
        
        payload = {
            "model": "sarvam-m",
            "prompt": "Hello",
            "max_tokens": 10
        }
        
        response = requests.post(
            f"{base_url}/llm/completion",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        return response.status_code == 200
    except:
        return False

def process_documents(file_paths, api_key, base_url, context_window=4500, max_tokens=512, chunk_size=1024):
    """Process uploaded PDF documents and create index"""
    try:
        # Test API connection first
        with st.spinner("Testing API connection..."):
            if not test_sarvam_api(api_key, base_url):
                st.error("❌ Failed to connect to Sarvam API. Please check your API key and base URL.")
                return False
            st.success("✅ API connection successful!")
        
        # Initialize Sarvam LLM
        llm = SarvamLLM(api_key=api_key, base_url=base_url)
        
        # Initialize embedding model
        embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")
        
        # Configure settings
        Settings.llm = llm
        Settings.embed_model = embed_model
        Settings.chunk_size = chunk_size
        Settings.chunk_overlap = 200
        
        # Load documents
        with st.spinner("Loading and processing documents..."):
            documents = SimpleDirectoryReader(input_files=file_paths).load_data()
            st.success(f"✅ Loaded {len(documents)} document chunks")
        
        # Create index
        with st.spinner("Creating search index..."):
            index = VectorStoreIndex.from_documents(
                documents,
                show_progress=True
            )
            
            # Create query engine
            query_engine = index.as_query_engine(
                similarity_top_k=3,
                response_mode="compact"
            )
            
            # Store in session state
            st.session_state.index = index
            st.session_state.query_engine = query_engine
            st.session_state.processing_complete = True
            
        return True
        
    except Exception as e:
        st.error(f"❌ Error processing documents: {str(e)}")
        return False

def main():
    # Title and description
    st.title("📚 PDF Q&A with Sarvam AI")
    st.markdown("""
    Upload your PDF documents and ask questions about their content using Sarvam AI. 
                
    """)
    st.markdown("Go to [Sarvam AI Dashboard](https://dashboard.sarvam.ai/key-management), make an account, get 1000 free credits, and enjoy.")

    
    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # API Key input
        api_key = st.text_input(
            "Sarvam API Key",
            type="password",
            value=st.session_state.api_key,
            help="Enter your Sarvam AI API key"
        )
        
        if api_key:
            st.session_state.api_key = api_key
        
        # Base URL input
        base_url = st.text_input(
            "Sarvam API Base URL",
            value=st.session_state.base_url,
            help="Default: https://api.sarvam.ai"
        )
        st.session_state.base_url = base_url
        
        # Test API button
        if api_key and base_url:
            if st.button("🔗 Test API Connection", type="secondary"):
                with st.spinner("Testing connection..."):
                    if test_sarvam_api(api_key, base_url):
                        st.success("✅ API connection successful!")
                    else:
                        st.error("❌ Failed to connect to API")
        
        st.divider()
        
        # Model settings
        st.subheader("Model Settings")
        
        context_window = st.slider(
            "Context Window Size",
            min_value=1024,
            max_value=8192,
            value=4500,
            step=256,
            help="Maximum context length for the model"
        )
        
        max_tokens = st.slider(
            "Max Response Tokens",
            min_value=64,
            max_value=2048,
            value=512,
            step=64,
            help="Maximum tokens in the response"
        )
        
        chunk_size = st.slider(
            "Chunk Size",
            min_value=256,
            max_value=4096,
            value=1024,
            step=256,
            help="Size of document chunks for processing"
        )
        
        st.divider()
        
        # System prompt
        st.subheader("Assistant Behavior")
        system_prompt = st.text_area(
            "System Prompt",
            value="""You are a helpful Q&A assistant. Answer questions based only on the provided documents. 
If the answer is not in the documents, say "I cannot find this information in the provided documents."
Provide clear, concise answers with relevant details from the documents.""",
            height=150
        )
        
        # Store in session state for query engine
        st.session_state.system_prompt = system_prompt
        
        st.divider()
        
        # Clear session button
        if st.button("🔄 Clear Session", type="secondary", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    
    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("📤 Upload Documents")
        
        # File uploader
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=['pdf'],
            accept_multiple_files=True,
            help="Upload one or more PDF documents"
        )
        
        if uploaded_files:
            st.session_state.uploaded_files = uploaded_files
            st.write(f"**Selected files:**")
            for file in uploaded_files:
                st.write(f"- {file.name} ({file.size / 1024:.1f} KB)")
        
        # Process button
        if st.session_state.uploaded_files and st.session_state.api_key:
            if st.button("🚀 Process Documents", type="primary", use_container_width=True):
                with st.spinner("Processing documents..."):
                    # Save files temporarily
                    file_paths, temp_dir = save_uploaded_files(st.session_state.uploaded_files)
                    
                    # Process documents
                    success = process_documents(
                        file_paths, 
                        st.session_state.api_key,
                        st.session_state.base_url,
                        context_window,
                        max_tokens,
                        chunk_size
                    )
                    
                    if success:
                        st.success("✅ Documents processed successfully! You can now ask questions.")
                    else:
                        st.error("❌ Failed to process documents")
        
        elif st.session_state.uploaded_files and not st.session_state.api_key:
            st.warning("⚠️ Please enter your Sarvam API key in the sidebar")
    
    with col2:
        st.header("💬 Ask Questions")
        
        if st.session_state.processing_complete:
            # Question input
            question = st.text_input(
                "Enter your question:",
                placeholder="e.g., What are the main findings of this document?",
                help="Ask anything about your uploaded documents"
            )
            
            # Advanced options
            with st.expander("⚡ Advanced Options"):
                temperature = st.slider(
                    "Temperature",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.1,
                    step=0.05,
                    help="Controls randomness (0 = deterministic)"
                )
                
                top_k = st.slider(
                    "Top K Retrieval",
                    min_value=1,
                    max_value=10,
                    value=3,
                    help="Number of document chunks to retrieve"
                )
            
            if question:
                if st.button("🔍 Get Answer", type="primary", use_container_width=True):
                    with st.spinner("Thinking..."):
                        try:
                            # Update query engine with new settings
                            st.session_state.query_engine = st.session_state.index.as_query_engine(
                                similarity_top_k=top_k,
                                response_mode="compact"
                            )
                            
                            # Add system prompt to question
                            enhanced_question = f"{st.session_state.system_prompt}\n\nQuestion: {question}"
                            
                            # Get response
                            response = st.session_state.query_engine.query(enhanced_question)
                            
                            # Display response
                            st.subheader("📝 Answer:")
                            st.write(str(response))
                            
                            # Show sources if available
                            if hasattr(response, 'source_nodes') and response.source_nodes:
                                with st.expander("📄 View Sources"):
                                    for i, node in enumerate(response.source_nodes[:3]):
                                        st.write(f"**Source {i+1}:**")
                                        st.text(node.text[:300] + "..." if len(node.text) > 300 else node.text)
                                        st.divider()
                            
                        except Exception as e:
                            st.error(f"❌ Error getting answer: {str(e)}")
        else:
            st.info("👈 Upload PDFs and enter your API key to start also adjust parameters for longer or shorter answers.")
    
    # Footer
    st.divider()
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style='text-align: center; padding: 20px;'>
                <p style='color: #666;'>Built with ❤️ using Sarvam AI and Streamlit</p>
                <p style='color: #888; font-size: 0.9em;'>Upload PDFs • Ask Questions • Get Answers</p>
            </div>
            """,
            unsafe_allow_html=True
        )

if __name__ == "__main__":
    main()