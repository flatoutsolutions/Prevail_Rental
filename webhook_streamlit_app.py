import streamlit as st
import requests
import json
import datetime
import os
import time
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
# In production, these will come from Streamlit secrets
load_dotenv()

# Initialize session state for storing conversation history and context
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """👋 Welcome to our Equipment Rental Assistant!

Hi, which equipment  do you need?
            "id": "welcome_message"
        }
    ]

# Get API keys from environment variables or secrets
def get_secret(key_name):
    if hasattr(st, "secrets") and key_name in st.secrets:
        return st.secrets[key_name]
    return os.getenv(key_name)

openai_api_key = get_secret("OPENAI_API_KEY")

# Set API keys in session state
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = openai_api_key
    
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None  # OpenAI thread ID
    
if "run_id" not in st.session_state:
    st.session_state.run_id = None  # OpenAI run ID
    
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = get_secret("OPENAI_ASSISTANT_ID")

# Constants for webhooks
WEBHOOK_URLS = {
    "get_products_list": "https://flatoutsolutions.app.n8n.cloud/webhook/get-products-list",
    "get_product_availability": "https://flatoutsolutions.app.n8n.cloud/webhook/get-product-availability",
    "create_order": "https://flatoutsolutions.app.n8n.cloud/webhook/create-order"
}

# Custom CSS to improve the appearance
st.markdown("""
<style>
    .main {
        background-color: #121212;
        color: white;
    }
    .stTextInput > div > div > input {
        background-color: #2a2a2a;
        color: white;
        border-radius: 20px;
        padding: 12px 20px;
        border: none;
    }
    .stButton > button {
        background-color: #ff4b4b;
        color: white;
        border-radius: 20px;
        border: none;
        padding: 8px 16px;
    }
    h1, h2, h3 {
        color: white !important;
    }
    .stChatMessage {
        background-color: #1e1e1e;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
    }
    .stChatMessage.user {
        background-color: #324b77;
    }
    .stChatMessage.assistant {
        background-color: #383838;
    }
    .stChatInputContainer {
        padding-top: 20px;
    }
    .css-1t42vg5 {
        gap: 20px;
    }
    .stMarkdown {
        color: #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# Streamlit UI setup
st.title("Rental Assistant")

# Initialize OpenAI client
def get_openai_client():
    return OpenAI(api_key=st.session_state.openai_api_key)

# Function to validate API keys are present
def validate_api_keys():
    if not st.session_state.openai_api_key:
        st.error("OpenAI API key not available. Please check your secrets configuration.")
        return False
    if not st.session_state.assistant_id:
        st.error("OpenAI Assistant ID not available. Please check your secrets configuration.")
        return False
    return True

# Webhook Helper Functions
def call_webhook(webhook_name, data=None):
    """Make a POST request to the n8n webhook"""
    if webhook_name not in WEBHOOK_URLS:
        return {"error": f"Webhook {webhook_name} not found"}
    
    url = WEBHOOK_URLS[webhook_name]
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Webhook Request Error: {e}")
        return {"error": str(e)}
    
def call_webhook_with_retry(webhook_name, data=None, max_retries=3, backoff_factor=0.5):
    """Make a POST request to the n8n webhook with retry capabilities for 500 errors"""
    if webhook_name not in WEBHOOK_URLS:
        return {"error": f"Webhook {webhook_name} not found"}
    
    url = WEBHOOK_URLS[webhook_name]
    
    for attempt in range(max_retries):
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            # Handle 500 errors with retry
            if e.response.status_code == 500 and attempt < max_retries - 1:
                # Calculate backoff time (exponential backoff)
                delay = backoff_factor * (2 ** attempt)
                
                # Wait before retrying
                time.sleep(delay)
                continue
            
            st.error(f"Webhook Request Error: {e}")
            return {"error": str(e)}
            
        except Exception as e:
            st.error(f"Webhook Request Error: {e}")
            return {"error": str(e)}

# Function definitions for assistant function calling
def list_product_groups():
    """Get a list of all product groups"""
    response = call_webhook_with_retry("get_products_list")
    
    if response and 'product_groups' in response:
        return {
            "product_groups": response["product_groups"],
            "total_count": len(response["product_groups"])
        }
    return {"error": "Failed to retrieve product groups", "response": response}

def get_product_details(product_group_id, from_date, to_date):
    """Get product details, availability and pricing"""
    # Format dates
    if isinstance(from_date, str):
        from_date_obj = datetime.datetime.strptime(from_date, "%Y-%m-%d")
        from_date_iso = from_date_obj.strftime("%Y-%m-%dT00:00:00Z")
    else:
        from_date_iso = from_date
        
    if isinstance(to_date, str):
        to_date_obj = datetime.datetime.strptime(to_date, "%Y-%m-%d")
        to_date_iso = to_date_obj.strftime("%Y-%m-%dT00:00:00Z")
    else:
        to_date_iso = to_date
    
    # Prepare data for the webhook
    data = {
        "call": {
            "call_id": "streamlit_app",
            "call_type": "web_app"
        },
        "name": "product_availability",
        "args": {
            "group_id": product_group_id,
            "from_date": from_date_iso,
            "till_date": to_date_iso
        }
    }
    
    # Call the webhook
    response = call_webhook_with_retry("get_product_availability", data)
    
    if response and "error" not in response:
        # Calculate rental duration in days
        from_date_obj = datetime.datetime.strptime(from_date, "%Y-%m-%d")
        to_date_obj = datetime.datetime.strptime(to_date, "%Y-%m-%d")
        rental_days = (to_date_obj - from_date_obj).days
        
        # If days is 0 (same day rental), set to 1
        if rental_days == 0:
            rental_days = 1
            
        # Calculate total price based on base price and days
        base_price = float(response.get("productBasePrice", 0))
        total_price = base_price * rental_days
            
        return {
            "product_id": response.get("productId"),
            "name": response.get("productName"),
            "availability": {
                "available": response.get("available", 0)
            },
            "pricing": {
                "base_price": base_price,
                "total_price": total_price,
                "rental_days": rental_days
            }
        }
    return {"error": "Failed to get product details", "response": response}

def create_reservation(customer_info, product_id, start_date, end_date, quantity=1):
    """Create a complete reservation"""
    # Format dates
    if isinstance(start_date, str):
        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        from_date_iso = start_date_obj.strftime("%Y-%m-%dT00:00:00")
    else:
        from_date_iso = start_date
        
    if isinstance(end_date, str):
        to_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        till_date_iso = to_date_obj.strftime("%Y-%m-%dT23:59:59")
    else:
        till_date_iso = end_date
    
    # Extract customer information
    name = customer_info.get("name", "")
    email = customer_info.get("email", "")
    phone = customer_info.get("phone", "")
    
    # Format phone with country code if it doesn't have one
    if phone and not phone.startswith("+"):
        phone = "+1" + phone.replace("-", "")
    
    # Prepare data for the webhook
    data = {
        "call": {
            "call_id": "streamlit_app",
            "call_type": "web_app"
        },
        "name": "create_order",
        "args": {
            "client_name": name,
            "client_email": email,
            "client_phone": phone,
            "product_id": product_id,
            "from_date": from_date_iso,
            "till_date": till_date_iso
        }
    }
    
    # Call the webhook
    response = call_webhook_with_retry("create_order", data)
    
    if response and "error" not in response:
        return {
            "success": True,
            "message": response.get("result", "Reservation completed successfully")
        }
    return {"error": "Failed to create reservation", "response": response}

# Function to execute assistant functions based on OpenAI's request
def execute_function(function_name, arguments):
    """Execute a function based on its name and arguments"""
    # Parse arguments
    args = json.loads(arguments)
    
    if function_name == "list_product_groups":
        return list_product_groups()
    
    elif function_name == "get_product_details":
        return get_product_details(
            args.get("product_group_id"),
            args.get("from_date"),
            args.get("to_date")
        )
    
    elif function_name == "create_reservation":
        customer_info = args.get("customer_info", {})
        return create_reservation(
            customer_info,
            args.get("product_id"),
            args.get("start_date"),
            args.get("end_date"),
            args.get("quantity", 1)
        )
    
    else:
        return {"error": f"Unknown function: {function_name}"}

# Create OpenAI Thread if not exists
def ensure_thread():
    if st.session_state.thread_id is None:
        client = get_openai_client()
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id

# Process an OpenAI run
def process_run():
    if not st.session_state.thread_id or not st.session_state.run_id:
        return False
    
    client = get_openai_client()
    
    try:
        # Check run status
        run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id,
            run_id=st.session_state.run_id
        )
        
        status = run.status
        
        if status == "requires_action":
            # Handle function calls
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                # Execute the function
                result = execute_function(function_name, function_args)
                
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(result)
                })
            
            # Submit outputs back to OpenAI
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=st.session_state.thread_id,
                run_id=st.session_state.run_id,
                tool_outputs=tool_outputs
            )
            return True  # Still processing
            
        elif status == "completed":
            # Get the latest messages
            last_message_id = None
            if st.session_state.messages and len(st.session_state.messages) > 0:
                if "id" in st.session_state.messages[-1]:
                    last_message_id = st.session_state.messages[-1]["id"]
            
            messages = client.beta.threads.messages.list(
                thread_id=st.session_state.thread_id,
                order="asc",
                after=last_message_id
            )
            
            # Add new messages to the UI
            for message in messages.data:
                if message.role == "assistant":
                    content = ""
                    for content_block in message.content:
                        if content_block.type == "text":
                            content += content_block.text.value
                    
                    # Check if this message is already in our history
                    message_exists = False
                    for m in st.session_state.messages:
                        if "id" in m and m["id"] == message.id:
                            message_exists = True
                            break
                    
                    if not message_exists:
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": content,
                            "id": message.id
                        })
                        st.rerun()  # Force refresh to show the new message
            
            st.session_state.run_id = None
            return False  # Processing complete
            
        elif status in ["failed", "cancelled", "expired"]:
            st.error(f"Run {status}")
            st.session_state.run_id = None
            return False  # Processing failed
            
        else:
            # Still running (queued, in_progress, etc.)
            return True
            
    except Exception as e:
        st.error(f"Error processing run: {e}")
        st.session_state.run_id = None
        return False

# Send a message to the assistant
def send_message(message):
    client = get_openai_client()
    
    ensure_thread()
    
    # Add user message to the UI
    st.session_state.messages.append({
        "role": "user",
        "content": message,
    })
    
    # Add the message to the thread
    client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=message
    )
    
    # Create a run
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=st.session_state.assistant_id
    )
    
    st.session_state.run_id = run.id

# Display chat messages
st.subheader("Chat with the Rental Assistant")

# Create a container with a custom background for the chat area
chat_container = st.container()
with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"], avatar="🤖" if message["role"] == "assistant" else None):
            # Use markdown for assistant messages to properly render HTML
            if message["role"] == "assistant":
                st.markdown(message["content"], unsafe_allow_html=True)
            else:
                st.write(message["content"])

# Process any ongoing run
if st.session_state.run_id:
    with st.spinner("🔄 Getting information..."):
        still_running = process_run()
        if still_running:
            time.sleep(1)  # Small delay to prevent hammering the API
            st.rerun()

# Styling for chat interface
st.markdown("""
<style>
    .stChatInput {
        padding: 10px 15px;
        border-radius: 25px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
        background-color: #2d2d2d;
    }
    
    /* Chat message container styling */
    .chat-container {
        max-width: 800px;
        margin: 0 auto;
        padding: 20px;
        background-color: #1a1a1a;
        border-radius: 10px;
        box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
    }
    
    /* Styling for user message bubbles */
    .user-message {
        background-color: #4a76a8;
        color: white;
        border-radius: 18px 18px 0 18px;
        padding: 12px 18px;
        margin: 8px 0;
        max-width: 80%;
        align-self: flex-end;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    }
    
    /* Styling for assistant message bubbles */
    .assistant-message {
        background-color: #383838;
        color: white;
        border-radius: 18px 18px 18px 0;
        padding: 12px 18px;
        margin: 8px 0;
        max-width: 80%;
        align-self: flex-start;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
    }
    
    /* Custom bottom bar */
    .bottom-bar {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #2d2d2d;
        padding: 15px 0;
        box-shadow: 0 -2px 10px rgba(0, 0, 0, 0.2);
        z-index: 1000;
    }
</style>
""", unsafe_allow_html=True)

# Input for new messages
user_input = st.chat_input("Ask about equipment, check availability, or book a rental...")
if user_input and validate_api_keys():
    send_message(user_input)
    st.rerun()