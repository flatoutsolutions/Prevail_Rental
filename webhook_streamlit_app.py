import streamlit as st
import requests
import json
import datetime
import os
import time
import logging
from openai import OpenAI
from dotenv import load_dotenv
from logging_enhancement import setup_logging

# Set up logging first
logger = setup_logging(log_file="rental_assistant.log", console_level=logging.INFO, file_level=logging.DEBUG)

logger.info("Application starting")

# Load environment variables from .env file
load_dotenv()
logger.info("Environment variables loaded")

# Import after logging is configured
from assistant_manager import AssistantManager
from logging_enhancement import setup_logging

# Set up logging
logger = setup_logging(log_file="rental_assistant.log", console_level=logging.INFO, file_level=logging.DEBUG)

logger.info("Application starting")

# Initialize session state for storing conversation history and context
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """👋 Welcome to our Equipment Rental Assistant!

Hi, which equipment  do you need?
""",
            "id": "welcome_message"
        }
    ]

# Get API keys from environment variables
openai_api_key = os.getenv("OPENAI_API_KEY")

# Set API keys in session state
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = openai_api_key
    
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None  # OpenAI thread ID
    
if "run_id" not in st.session_state:
    st.session_state.run_id = None  # OpenAI run ID
    
if "assistant_manager" not in st.session_state:
    st.session_state.assistant_manager = None

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

# Only show API key inputs if not provided in environment
if not openai_api_key:
    with st.sidebar:
        st.header("API Configuration")
            
        openai_api_key_input = st.text_input("OpenAI API Key", 
                                value=st.session_state.openai_api_key, 
                                type="password")
        st.session_state.openai_api_key = openai_api_key_input
        
        if st.button("Initialize Assistant"):
            try:
                with st.spinner("Creating assistant..."):
                    # Initialize AssistantManager with API key
                    assistant_manager = AssistantManager(api_key=st.session_state.openai_api_key)
                    # Create or get the assistant
                    assistant_id = assistant_manager.get_or_create_assistant()
                    st.session_state.assistant_manager = assistant_manager
                    st.success(f"Assistant initialized with ID: {assistant_id}")
                    st.rerun()
            except Exception as e:
                st.error(f"Error initializing assistant: {e}")

# Function to validate API keys are present
def validate_api_keys():
    if not st.session_state.openai_api_key:
        st.error("OpenAI API key not set. Please set it in the .env file or in the sidebar.")
        return False
    return True

def call_webhook(webhook_name, data=None):
    """Make a POST request to the n8n webhook"""
    if webhook_name not in WEBHOOK_URLS:
        logger.error(f"Webhook {webhook_name} not found")
        return {"error": f"Webhook {webhook_name} not found"}
    
    url = WEBHOOK_URLS[webhook_name]
    
    try:
        # Log details
        logger.info(f"Making POST request to webhook: {url}")
        if data:
            logger.debug(f"Webhook data: {json.dumps(data, indent=2, default=str)}")
            
        response = requests.post(url, json=data)
        response.raise_for_status()
        
        # Log response
        logger.debug(f"Webhook response: {json.dumps(response.json(), indent=2)}")
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"Webhook Request Error: {e}", exc_info=True)
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            logger.error(f"Error response content: {e.response.text}")
        st.error(f"Webhook Request Error: {e}")
        return {"error": str(e)}
    except requests.exceptions.RequestException as e:
        logger.error(f"Webhook Request Error: {e}", exc_info=True)
        st.error(f"Webhook Request Error: {e}")
        return {"error": str(e)}
    
def call_webhook_with_retry(webhook_name, data=None, max_retries=3, backoff_factor=0.5):
    """
    Make a POST request to the n8n webhook with retry capabilities for 500 errors
    
    Args:
        webhook_name: Name of the webhook to call
        data: JSON data to send to the webhook
        max_retries: Maximum number of retry attempts (default: 3)
        backoff_factor: Backoff factor for retry delay (default: 0.5)
        
    Returns:
        Response JSON or error dictionary
    """
    if webhook_name not in WEBHOOK_URLS:
        logger.error(f"Webhook {webhook_name} not found")
        return {"error": f"Webhook {webhook_name} not found"}
    
    url = WEBHOOK_URLS[webhook_name]
    
    for attempt in range(max_retries):
        try:
            # Log details
            logger.info(f"Making POST request to webhook: {url} (Attempt {attempt+1}/{max_retries})")
            if data:
                logger.debug(f"Webhook data: {json.dumps(data, indent=2, default=str)}")
                
            response = requests.post(url, json=data)
            response.raise_for_status()
            
            # Log response
            logger.debug(f"Webhook response: {json.dumps(response.json(), indent=2)}")
            return response.json()
        
        except requests.exceptions.HTTPError as e:
            # Handle 500 errors with retry
            if e.response.status_code == 500 and attempt < max_retries - 1:
                # Calculate backoff time (exponential backoff)
                delay = backoff_factor * (2 ** attempt)
                
                logger.warning(f"Webhook returned 500, retrying in {delay:.1f}s (Attempt {attempt+1}/{max_retries})")
                logger.debug(f"Response content: {e.response.text}")
                
                # Wait before retrying
                time.sleep(delay)
                continue
            
            # Log the final error
            logger.error(f"Webhook Request Error: {e}", exc_info=True)
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Error response content: {e.response.text}")
            
            st.error(f"Webhook Request Error: {e}")
            return {"error": str(e)}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook Request Error: {e}", exc_info=True)
            st.error(f"Webhook Request Error: {e}")
            return {"error": str(e)}

# Function definitions for assistant function calling

def list_product_groups():
    """Get a list of all product groups"""
    # Call the products list webhook instead of direct API
    response = call_webhook_with_retry("get_products_list")
    
    if response and 'product_groups' in response:
        logger.info(f"Retrieved {len(response['product_groups'])} product groups")
        return {
            "product_groups": response["product_groups"],
            "total_count": len(response["product_groups"])
        }
    return {"error": "Failed to retrieve product groups", "response": response}

def get_product_details(product_group_id, from_date, to_date):
    """Get product details, availability and pricing - replaces multiple API calls"""
    # Format dates
    try:
        if isinstance(from_date, str):
            from_date_obj = datetime.datetime.strptime(from_date, "%Y-%m-%d")
            # Format as ISO8601 format with Z suffix for UTC
            from_date_iso = from_date_obj.strftime("%Y-%m-%dT00:00:00Z")
        else:
            from_date_iso = from_date
            
        if isinstance(to_date, str):
            to_date_obj = datetime.datetime.strptime(to_date, "%Y-%m-%d")
            # Format as ISO8601 format with Z suffix for UTC
            to_date_iso = to_date_obj.strftime("%Y-%m-%dT00:00:00Z")
        else:
            to_date_iso = to_date
        
        # Prepare data for the webhook - match the expected format
        data = {
            "call": {
                "call_id": "streamlit_app",  # Use a dummy call ID since we're not in a call
                "call_type": "web_app"       # Indicate this is from web app not voice
            },
            "name": "product_availability",
            "args": {
                "group_id": product_group_id,   # Use group_id instead of product_group_id
                "from_date": from_date_iso,     # Use ISO format
                "till_date": to_date_iso        # Use till_date instead of to_date
            }
        }
        
        logger.info(f"Checking availability for product {product_group_id} from {from_date} to {to_date}")
        logger.debug(f"Webhook payload format: {json.dumps(data, indent=2, default=str)}")
        
        # Call the webhook with retry for 500 errors
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
            
            logger.info(f"Product available: {response.get('available', 0)} units, base price: {base_price}, days: {rental_days}, total: {total_price}")
                
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
    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}", exc_info=True)
        return {"error": f"Error getting product details: {str(e)}"}
    
def create_reservation(customer_info, product_id, start_date, end_date, quantity=1):
    """Create a complete reservation - replaces multiple API calls"""
    try:
        # Format dates
        if isinstance(start_date, str):
            start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            # Format as ISO8601 format with Z suffix for UTC
            from_date_iso = start_date_obj.strftime("%Y-%m-%dT00:00:00")
        else:
            from_date_iso = start_date
            
        if isinstance(end_date, str):
            to_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            # Format as ISO8601 format with Z suffix for UTC
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
        
        # Prepare data for the webhook - match the expected format
        data = {
            "call": {
                "call_id": "streamlit_app",  # Use a dummy call ID since we're not in a call
                "call_type": "web_app"       # Indicate this is from web app not voice
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
        
        logger.info(f"Creating reservation for product {product_id}, customer: {name}")
        logger.debug(f"Webhook payload format: {json.dumps(data, indent=2, default=str)}")
        
        # Call the webhook with retry for 500 errors
        response = call_webhook_with_retry("create_order", data)
        
        if response and "error" not in response:
            logger.info(f"Reservation created successfully: {response.get('result', 'Success')}")
            return {
                "success": True,
                "message": response.get("result", "Reservation completed successfully")
            }
        return {"error": "Failed to create reservation", "response": response}
    except Exception as e:
        logger.error(f"Error creating reservation: {str(e)}", exc_info=True)
        return {"error": f"Error creating reservation: {str(e)}"}

# Function to execute assistant functions based on OpenAI's request
def execute_function(function_name, arguments):
    """Execute a function based on its name and arguments"""
    # Parse arguments
    logger.info(f"Executing function: {function_name}")
    logger.debug(f"Function arguments: {arguments}")
    
    try:
        args = json.loads(arguments)
        
        if function_name == "list_product_groups":
            logger.info("Calling list_product_groups")
            result = list_product_groups()
            logger.debug(f"list_product_groups result: {json.dumps(result, indent=2, default=str)}")
            return result
        
        elif function_name == "get_product_details":
            logger.info(f"Calling get_product_details for product {args.get('product_group_id')}")
            result = get_product_details(
                args.get("product_group_id"),
                args.get("from_date"),
                args.get("to_date")
            )
            logger.debug(f"get_product_details result: {json.dumps(result, indent=2, default=str)}")
            return result
        
        elif function_name == "create_reservation":
            customer_info = args.get("customer_info", {})
            logger.info(f"Calling create_reservation for customer {customer_info.get('name')}")
            result = create_reservation(
                customer_info,
                args.get("product_id"),
                args.get("start_date"),
                args.get("end_date"),
                args.get("quantity", 1)
            )
            logger.debug(f"create_reservation result: {json.dumps(result, indent=2, default=str)}")
            return result
        
        else:
            logger.warning(f"Unknown function called: {function_name}")
            return {"error": f"Unknown function: {function_name}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}", exc_info=True)
        return {"error": f"Invalid JSON in arguments: {e}"}
    except Exception as e:
        logger.error(f"Error executing function {function_name}: {e}", exc_info=True)
        return {"error": f"Error executing function: {str(e)}"}

# Create OpenAI Thread if not exists
def ensure_thread():
    if not st.session_state.assistant_manager:
        return
        
    if st.session_state.thread_id is None:
        try:
            thread_id = st.session_state.assistant_manager.create_thread()
            st.session_state.thread_id = thread_id
            print(f"Created new thread: {thread_id}")
        except Exception as e:
            st.error(f"Error creating thread: {e}")

# Process an OpenAI run
def process_run():
    if not st.session_state.assistant_manager:
        logger.warning("Cannot process run: Assistant manager not initialized")
        return False
    
    if not st.session_state.thread_id or not st.session_state.run_id:
        logger.warning("Cannot process run: Missing thread_id or run_id")
        return False
    
    try:
        # Check run status
        logger.info(f"Checking run status for run {st.session_state.run_id}")
        status = st.session_state.assistant_manager.get_run_status(
            st.session_state.thread_id,
            st.session_state.run_id
        )
        
        logger.info(f"Run status: {status}")
        
        if status == "requires_action":
            logger.info("Run requires action, handling function calls")
            # Handle function calls using our execute_function
            st.session_state.assistant_manager.handle_required_actions(
                st.session_state.thread_id,
                st.session_state.run_id,
                execute_function
            )
            return True  # Still processing
            
        elif status == "completed":
            logger.info("Run completed, retrieving messages")
            # Get the latest messages
            last_message_id = None
            if st.session_state.messages and len(st.session_state.messages) > 0:
                if "id" in st.session_state.messages[-1]:
                    last_message_id = st.session_state.messages[-1]["id"]
            
            messages = st.session_state.assistant_manager.get_thread_messages(
                st.session_state.thread_id,
                order="asc",
                after=last_message_id
            )
            
            logger.debug(f"Retrieved {len(messages)} new messages")
            
            # Add new messages to the UI
            for message in messages:
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
                        logger.info(f"Adding new assistant message: {message.id}")
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": content,
                            "id": message.id
                        })
                        st.rerun()  # Force refresh to show the new message
            
            st.session_state.run_id = None
            return False  # Processing complete
            
        elif status in ["failed", "cancelled", "expired"]:
            logger.error(f"Run {status}")
            st.error(f"Run {status}")
            st.session_state.run_id = None
            return False  # Processing failed
            
        else:
            # Still running (queued, in_progress, etc.)
            logger.debug(f"Run still in progress with status: {status}")
            return True
            
    except Exception as e:
        logger.error(f"Error processing run: {e}", exc_info=True)
        st.error(f"Error processing run: {e}")
        st.session_state.run_id = None
        return False

# Send a message to the assistant
def send_message(message):
    if not st.session_state.assistant_manager:
        st.error("Assistant not initialized. Please initialize the assistant first.")
        return
    
    ensure_thread()
    
    # Add user message to the UI
    st.session_state.messages.append({
        "role": "user",
        "content": message,
        # No id for user messages initially
    })
    
    try:
        # Add the message to the thread
        st.session_state.assistant_manager.add_message_to_thread(
            st.session_state.thread_id,
            message
        )
        
        # Create a run
        run_id = st.session_state.assistant_manager.run_assistant(
            st.session_state.thread_id
        )
        
        st.session_state.run_id = run_id
    except Exception as e:
        st.error(f"Error sending message: {e}")

# Initialize the assistant manager on app start - only once for the entire Streamlit app
if validate_api_keys():
    # Check if we already have the assistant manager in session state
    if "assistant_manager" not in st.session_state or st.session_state.assistant_manager is None:
        try:
            with st.spinner("Initializing assistant..."):
                # Thanks to the singleton pattern, this will either:
                # 1. Create a new AssistantManager if it's the first time, or
                # 2. Return the existing instance if it was already created
                logger.info("Initializing AssistantManager")
                assistant_manager = AssistantManager(api_key=st.session_state.openai_api_key)
                assistant_id = assistant_manager.get_or_create_assistant()
                st.session_state.assistant_manager = assistant_manager
                logger.info(f"Assistant initialized with ID: {assistant_id}")
        except Exception as e:
            logger.error(f"Error initializing assistant: {e}", exc_info=True)
            st.error(f"Error initializing assistant: {e}")

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
if user_input:
    if st.session_state.assistant_manager:
        send_message(user_input)
        st.rerun()
    else:
        st.error("Assistant not initialized. Please initialize the assistant first.")