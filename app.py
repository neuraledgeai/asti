# --- Import libraries ---
import streamlit as st
from together import Together
from PyPDF2 import PdfReader
from docx import Document
import re
from serpapi import GoogleSearch
from os import environ
from io import BytesIO
from elevenlabs import ElevenLabs


# --- Streamlit Page Configuration ---
st.set_page_config(
    page_title="Asti",
    layout="wide",
    page_icon="🌟"
)

# --- Sidebar Navigation ---
st.sidebar.page_link("app.py", label="Chat", icon="💬")

# --- API Key & Client Initialization ---
api_key = environ.get("API_KEY")
client = Together(api_key=api_key)
serp_api_key = environ.get("SERP_API_KEY")
elevenlabs_api_key = environ.get("ELEVENLABS_API_KEY")

# --- LLM Model Definitions ---
META_MODEL = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
DEEPSEEK_MODEL = "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"

# --- Web Search Function ---
def fetch_snippets(query, api_key):
    params = {"engine": "google", "q": query, "api_key": api_key}
    search = GoogleSearch(params)
    results = search.get_dict()
    organic_results = results.get("organic_results", [])
    snippets_with_sources = []
    
    for i in organic_results:
        snippet = i.get("snippet", "")
        source = i.get("source", "Unknown Source")
        link = i.get("link", "#")
        
        if snippet:
            linked_source = f"[{source}]({link})"
            snippets_with_sources.append(f"{snippet} ({linked_source})")

    return " ".join(snippets_with_sources) if snippets_with_sources else "No relevant information found."

# --- Document Text Extraction Functions ---
def read_pdf(file):
    pdf_reader = PdfReader(file)
    text = "\n\n".join(
        page.extract_text().strip()
        for page in pdf_reader.pages
        if page.extract_text()
    )
    return f"User uploaded a PDF document. Here are the contents of it:\n\n{text}"

# Functions to extract text from word files
def read_word(file):
    doc = Document(file)
    text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
    return f"User uploaded a Word document. Here are the contents of it:\n\n{text}"

# --- Session State Initialization ---
if "messages" not in st.session_state:
    st.session_state.messages = [] # Stores chat history
if "document_content" not in st.session_state:
    st.session_state.document_content = None # Stores text content of the uploaded study material
if "selected_model" not in st.session_state:
    st.session_state.selected_model = META_MODEL # Stores the currently active LLM mode

# --- File Upload Section ---
with st.expander("📄 Upload Your Study Material (Optional)", expanded=True):
    uploaded_file = st.file_uploader("Upload a PDF or Word file", type=["pdf", "docx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith(".pdf"):
                st.session_state.document_content = read_pdf(uploaded_file)
            elif uploaded_file.name.endswith(".docx"):
                st.session_state.document_content = read_word(uploaded_file)
            st.success("✅ Document uploaded successfully! You can now start chatting.")

            # Suggested prompt buttons
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("📄 Summarize"):
                    st.session_state.prefill_input = "Please provide a concise and *highly readable* summary of the entire contents of the uploaded document."
            with col2:
                if st.button("🧠 Make Quiz"):
                    st.session_state.prefill_input = "Create a comprehensive quiz based *only* on the content of the uploaded document."
            with col3:
                if st.button("📚 Explain"):
                    st.session_state.prefill_input = "Identify and explain *comprehensively* the key concepts and important ideas present in the uploaded document."
            with col4:
                if st.button("🗺️ Roadmap"):
                    st.session_state.prefill_input = "Based on the content of the uploaded document, create a structured learning roadmap to comprehensively understand the main subject matter. Organize the learning path into logical, digestible segments that are appropriate for the nature of the document's contents. For each segment, identify the core concepts, important ideas, and potential skills a student should acquire from the document's content. Present this roadmap as a clear, step-by-step learning path. Guide the learning journey."
        except Exception as e:
            st.error(f"❌ Error reading file: {e}")

# --- AI Mode Selection ---
model_choice = st.segmented_control(
    "",
    options=["Default", "Reason", "Web Search"],
    format_func=lambda x: "Reason" if x == "Reason" else "Web Search" if x == "Web Search" else "Turbo Chat",
    default="Default"
)
st.session_state.selected_model = (
    DEEPSEEK_MODEL if model_choice == "Reason" else META_MODEL if model_choice == "Web Search" else META_MODEL # META_MODEL for Turbo Chat and Web Search.
)

# --- Chat History Display ---
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

#
# --- Dynamic Chat Input Placeholder ---
placeholder = ""

if model_choice == "Web Search":
    placeholder = "Search the web for information or a topic..."
elif model_choice == "Reason":
    if st.session_state.document_content:
        placeholder = "Ask a question requiring deeper thought about your document..."
    else:
        placeholder = "Ask a question that requires deeper thought..."
else: # Default (Turbo Chat) Mode
    if st.session_state.document_content:
        placeholder = "Ask about your document or chat generally..."
    else:
        placeholder = "Type your message here..." # Or "Ask me anything..."

# --- Main Chat Input & Response Generation ---
prefill_text = st.session_state.get("prefill_input", "")
user_input = st.chat_input(placeholder)

if user_input is None and prefill_text:
    # Simulate the prefilled input only if no user input and prefill exists
    user_input = prefill_text

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.prefill_input = ""  # Clear after using

    with st.chat_message("user"):
        st.markdown(user_input)

    response_placeholder = st.empty()
    full_response = ""

    if model_choice == "Web Search":
        # Logic for Web Search mode: Model decides if search is needed, refines query, then uses results.

        # **Step 1: Ask Model If a Search is Required**
        decision_prompt = (
            "Hi this is for our chatbot system, it has primarily two options, one is normal chat mode and the other is chat enabled web search mode."
            f"Now the user has switched on Web Search mode (where we will search on the web, like Google Search, and get information) and asked us this : '{user_input}'."
            "Please understand that each web search has a cost. We need to minimize this cost. That we need to search the web only if the user has really need one."            
            "So that is your duty. You must understand it from the user input. Analyze that whether for this the user really requires an internet search."
            "If they really require we will search the internet and provide latest and relevant information, if not we will provide information from our databases."            
            "So if yes, reply with 'YES'. If not, reply with 'NO'. Remember, only reply with 'YES' or 'NO', because that is our code for this here."
        )
        
        decision_response = client.chat.completions.create(
            model=META_MODEL,
            messages=[{"role": "system", "content": decision_prompt}]
        )
        
        decision_text = decision_response.choices[0].message.content.strip().upper()

        if decision_text == "YES":
            # **Step 2: Generate a Proper Search Query**
            refine_prompt = f"User's request: {user_input}. Generate a single concise search query."
            refine_response = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": refine_prompt}]
            )
            
            search_query = refine_response.choices[0].message.content.strip()
            search_results = fetch_snippets(search_query, serp_api_key)
            
            # **Step 3: Generate the Final Response**
            final_prompt = f"Query: {user_input}. Search Results: {search_results}. Please frame an appropriate output from this. Make it very informative and engaging with appropriate boldness and linked texts. No headings for now."
            stream = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": final_prompt}],
                stream=True,
            )

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})
        else:
            # If no web search needed, generate a standard AI response.
            normal_prompt = f"User: {user_input}. Respond naturally."
            normal_response = client.chat.completions.create(
                model=META_MODEL,
                messages=[{"role": "system", "content": normal_prompt}],
                stream=True,
            )

            for chunk in normal_response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})

    else:
        # Turbo Chat & Reason Modes (No Web Search Logic)
        messages_with_context = [{"role": "system", "content": st.session_state.document_content}] if st.session_state.document_content else []
        messages_with_context.extend(st.session_state.messages)

        try:
            stream = client.chat.completions.create(
                model=st.session_state.selected_model,
                messages=messages_with_context,
                stream=True,
            )

            think_content = None

            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content

            # Special handling for 'Reason' mode: Extract and display model's thought process.
            if model_choice == "Reason":
                think_match = re.search(r"<think>(.*?)</think>", full_response, re.DOTALL)
                if think_match:
                    think_content = think_match.group(1).strip()
                clean_response = re.sub(r"<think>.*?</think>", "", full_response, flags=re.DOTALL).strip()
            else:
                clean_response = full_response.strip()

            response_placeholder.markdown(clean_response)
            st.session_state.messages.append({"role": "assistant", "content": clean_response})

            if think_content:
                with st.expander("🤔 Model's Thought Process"):
                    st.markdown(think_content)

        except Exception as e:
            error_message = str(e)
            if "Input validation error" in error_message and "tokens" in error_message:
                st.warning("⚠️ Too much text, token limit reached. Start a new chat to continue.")

# --- Voice Overview Feature ---
# Displays voice overview options in the sidebar if a document is uploaded.
if st.session_state.get("document_content"):
    with st.sidebar:
        st.markdown("Voice Overview")
        # Language selection
        language = st.radio("Select output language:", ["English", "Hindi"], index=1)

        if st.button("Generate Voice Overview"):
            elevenlabs = ElevenLabs(api_key = elevenlabs_api_key)
            with st.spinner("Generating voice script..."):
                prompt = (
                    f"The user uploaded a document. Please create a short, powerful, and engaging voice overview summarizing it "
                    f"in a narrative tone suitable for voiceover. Focus on clarity, tone, and engaging style. "
                    f"Please write the summary in **{language}** language.\n\n"
                    f"Here are the document contents:\n{st.session_state.document_content}"
                )
                try:
                    voice_response = client.chat.completions.create(
                        model=META_MODEL,
                        messages=[{"role": "system", "content": prompt}]
                    )
                    voice_script = voice_response.choices[0].message.content.strip()
                    st.session_state.voice_script = voice_script
                except Exception as e:
                    error_message = str(e)
                    if "Input validation error" in error_message and "tokens" in error_message:
                        st.warning("⚠️ Too much text, token limit reached. Start a new chat or upload a smaller document.")
                    else:
                        st.error(f"❌ Error generating voice script: {error_message}")

            with st.spinner("Generating audio..."):
                audio_gen = elevenlabs.text_to_speech.convert(
                    text=st.session_state.voice_script,
                    voice_id="nPczCjzI2devNBz1zQrb", 
                    model_id="eleven_flash_v2_5",
                    output_format="mp3_44100_128"
                )
                audio_bytes = b''.join(audio_gen)
                audio_buffer = BytesIO(audio_bytes)
                st.audio(audio_buffer, format="audio/mp3")
