import streamlit as st
import requests
import json
import datetime
from openai import OpenAI
import re
from typing import Dict, List, Any, Optional
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize session state for storing conversation history and context
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": """👋 Welcome to our Equipment Rental Assistant!

I'm here to help you rent equipment for your next project. I can help you with:

<ul>
<li>Browsing available equipment categories</li>
<li>Checking detailed information about specific products</li>
<li>Verifying availability for your desired dates</li>
<li>Providing pricing information for different rental durations</li>
<li>Creating a customer profile for you</li>
<li>Booking equipment for your project</li>
</ul>

Just let me know what you're looking for, and I'll guide you through the process!
""",
            "id": "welcome_message"
        }
    ]

# Get API keys from environment variables
booqable_api_key = os.getenv("BOOQABLE_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
assistant_id = os.getenv("OPENAI_ASSISTANT_ID")

# Set API keys in session state
if "api_key" not in st.session_state:
    st.session_state.api_key = booqable_api_key
    
if "openai_api_key" not in st.session_state:
    st.session_state.openai_api_key = openai_api_key
    
if "assistant_id" not in st.session_state:
    st.session_state.assistant_id = assistant_id
    
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None  # OpenAI thread ID
    
if "run_id" not in st.session_state:
    st.session_state.run_id = None  # OpenAI run ID

# Constants
BASE_URL = "https://flatout-solutions.booqable.com/api/1"

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
if not all([booqable_api_key, openai_api_key, assistant_id]):
    with st.sidebar:
        st.header("API Configuration")
        if not booqable_api_key:
            booqable_api_key_input = st.text_input("Booqable API Key", 
                                        value=st.session_state.api_key, 
                                        type="password")
            st.session_state.api_key = booqable_api_key_input
            
        if not openai_api_key:
            openai_api_key_input = st.text_input("OpenAI API Key", 
                                    value=st.session_state.openai_api_key, 
                                    type="password")
            st.session_state.openai_api_key = openai_api_key_input
            
        if not assistant_id:
            assistant_id_input = st.text_input("OpenAI Assistant ID", 
                                value=st.session_state.assistant_id)
            st.session_state.assistant_id = assistant_id_input

# Initialize OpenAI client
def get_openai_client():
    if not st.session_state.openai_api_key:
        st.error("Please enter your OpenAI API key in the sidebar.")
        return None
    
    return OpenAI(api_key=st.session_state.openai_api_key)

# Function to validate API keys are present
def validate_api_keys():
    if not st.session_state.api_key:
        st.error("Booqable API key not set. Please set it in the .env file or in the sidebar.")
        return False
    if not st.session_state.openai_api_key:
        st.error("OpenAI API key not set. Please set it in the .env file or in the sidebar.")
        return False
    if not st.session_state.assistant_id:
        st.error("OpenAI Assistant ID not set. Please set it in the .env file or in the sidebar.")
        return False
    return True

# Create OpenAI Thread if not exists
def ensure_thread():
    if st.session_state.thread_id is None:
        client = get_openai_client()
        if client:
            thread = client.beta.threads.create()
            st.session_state.thread_id = thread.id

# API Helper Functions
def make_api_request(endpoint, method="GET", data=None, params=None):
    """Make an API request to the Booqable API"""
    if not st.session_state.api_key:
        print("API key not set")
        return None
    
    # Ensure params includes the API key
    if params is None:
        params = {}
    params["api_key"] = st.session_state.api_key
    
    url = f"{BASE_URL}/{endpoint}"
    
    try:
        # Log to terminal only
        print(f"Making {method} request to: {url}")
        print(f"Parameters: {params}")
        if data:
            print(f"Data: {json.dumps(data, indent=2)}")
            
        if method == "GET":
            response = requests.get(url, params=params)
        elif method == "POST":
            response = requests.post(url, json=data, params=params)
        else:
            print(f"Unsupported method: {method}")
            return None
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        st.error(f"API Request Error: {e}")  # Keep error in UI for user awareness
        return None

# Function definitions for OpenAI Assistant function calling

def list_product_groups():
    """Get a list of all product groups"""
    response = make_api_request("product_groups")
    if response and 'product_groups' in response:
        return {
            "product_groups": [
                {
                    "id": group["id"],
                    "name": group["name"],
                    "slug": group["slug"],
                    "description": group.get("description"),
                    "base_price": group.get("base_price"),
                    "stock_count": group.get("stock_count"),
                    "photo_url": group.get("photo_url")
                }
                for group in response["product_groups"]
            ],
            "total_count": response["meta"]["total_count"]
        }
    return {"error": "Failed to retrieve product groups"}

def get_product_group(product_group_id):
    """Get details of a specific product group"""
    response = make_api_request(f"product_groups/{product_group_id}")
    if response and 'product_group' in response:
        product_group = response["product_group"]
        # Extract product IDs from the product group response
        products = []
        if "products" in product_group:
            for product in product_group["products"]:
                stock_items = []
                if "stock_items" in product:
                    for item in product["stock_items"]:
                        stock_items.append({
                            "id": item["id"],
                            "identifier": item["identifier"],
                            "status": item["status"]
                        })
                
                products.append({
                    "id": product["id"],
                    "name": product["name"],
                    "price": product.get("base_price"),
                    "stock_count": product.get("stock_counts", {}).get("total", 0),
                    "stock_items": stock_items
                })
        
        return {
            "id": product_group["id"],
            "name": product_group["name"],
            "description": product_group.get("description"),
            "price": product_group.get("base_price"),
            "products": products
        }
    return {"error": "Failed to retrieve product group details"}

def check_availability(product_id, from_date, to_date):
    """Check availability of a product for specific dates"""
    # Format dates for the API
    try:
        # Print debugging information
        print(f"Checking availability for product_id: {product_id}")
        print(f"From date: {from_date}, To date: {to_date}")
        
        # The error is likely because we're using the product_group_id instead of the product_id
        # Let's try to get the product_id first if we have a product_group_id
        if product_id:
            product_group = get_product_group(product_id)
            if product_group and "error" not in product_group and "products" in product_group and len(product_group["products"]) > 0:
                # Use the first product's ID instead of the product group ID
                product_id = product_group["products"][0]["id"]
                print(f"Using product ID: {product_id} instead of product group ID")
        
        # Convert dates to DD-MM-YYYY format required by the API
        if isinstance(from_date, str):
            from_date_obj = datetime.datetime.strptime(from_date, "%Y-%m-%d")
            from_date = from_date_obj.strftime("%d-%m-%Y")
        if isinstance(to_date, str):
            to_date_obj = datetime.datetime.strptime(to_date, "%Y-%m-%d")
            to_date = to_date_obj.strftime("%d-%m-%Y")
        
        params = {
            "from": from_date,
            "till": to_date
        }
        
        response = make_api_request(f"products/{product_id}/availability", params=params)
        if response:
            return {
                "available": response.get("available", 0),
                "stock_count": response.get("stock_count", 0),
                "needed": response.get("needed", 0),
                "planned": response.get("planned", 0)
            }
        return {"error": "Failed to check availability"}
    except Exception as e:
        print(f"Error checking availability: {str(e)}")
        return {"error": f"Error checking availability: {str(e)}"}

def get_product_pricing(product_id):
    """Get pricing structure for a product"""
    try:
        print(f"Getting pricing for product ID: {product_id}")
        
        # Check if we were given a product group ID instead of a product ID
        product_group = get_product_group(product_id)
        if product_group and "error" not in product_group and "products" in product_group and len(product_group["products"]) > 0:
            # Get the first product's ID
            actual_product_id = product_group["products"][0]["id"]
            print(f"Using product ID: {actual_product_id} instead of product group ID")
            product_id = actual_product_id
        
        response = make_api_request(f"products/{product_id}/prices")
        if response and 'price_structures' in response:
            pricing = []
            for structure in response["price_structures"]:
                if "tiles" in structure:
                    for tile in structure["tiles"]:
                        pricing.append({
                            "name": tile.get("name"),
                            "period": tile.get("period"),
                            "quantity": tile.get("quantity"),
                            "price_in_cents": tile.get("price_in_cents"),
                            "price": float(tile.get("price_in_cents", 0)) / 100
                        })
            return {"pricing": pricing}
        return {"error": "Failed to retrieve pricing information"}
    except Exception as e:
        print(f"Error getting pricing: {str(e)}")
        return {"error": f"Error getting pricing: {str(e)}"}

def create_customer(name, email, address1, address2, city, zipcode, country, phone):
    """Create a new customer profile"""
    customer_data = {
        "customer": {
            "name": name,
            "email": email,
            "properties_attributes": [
                {
                    "type": "Property::Address",
                    "name": "Main",
                    "address1": address1,
                    "address2": address2,
                    "zipcode": zipcode,
                    "city": city,
                    "country": country
                },
                {
                    "type": "Property::Phone",
                    "name": "Phone",
                    "value": phone
                }
            ]
        }
    }
    
    response = make_api_request("customers", method="POST", data=customer_data)
    if response and 'customer' in response:
        return {
            "customer_id": response["customer"]["id"],
            "name": response["customer"]["name"],
            "email": response["customer"]["email"]
        }
    return {"error": "Failed to create customer"}

def create_order(customer_id, start_date, end_date):
    """Create a new order for a customer"""
    # Format dates as required by the API (DD-MM-YYYY HH:MM)
    try:
        if isinstance(start_date, str):
            start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            start_time = start_date_obj.strftime("%d-%m-%Y %H:%M")
        else:
            start_time = start_date
            
        if isinstance(end_date, str):
            end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
            end_time = end_date_obj.strftime("%d-%m-%Y %H:%M")
        else:
            end_time = end_date
        
        order_data = {
            "order": {
                "customer_id": customer_id,
                "starts_at": start_time,
                "stops_at": end_time
            }
        }
        
        response = make_api_request("orders", method="POST", data=order_data)
        if response and 'order' in response:
            return {
                "order_id": response["order"]["id"],
                "status": response["order"]["status"],
                "starts_at": response["order"]["starts_at"],
                "stops_at": response["order"]["stops_at"]
            }
        return {"error": "Failed to create order"}
    except Exception as e:
        return {"error": f"Error creating order: {str(e)}"}

def book_order(order_id, product_id, quantity=1):
    """Book an order with specific products"""
    try:
        print(f"Booking order: {order_id} with product: {product_id}")
        
        # Check if we were given a product group ID instead of a product ID
        # We need to get the actual product ID from the product group
        product_group = get_product_group(product_id)
        if product_group and "error" not in product_group and "products" in product_group and len(product_group["products"]) > 0:
            # Get the first product's ID from the product group
            actual_product_id = product_group["products"][0]["id"]
            print(f"Using product ID: {actual_product_id} instead of product group ID")
            
            booking_data = {
                "ids": {
                    actual_product_id: quantity
                }
            }
        else:
            # Use the provided ID (assuming it's already a product ID)
            booking_data = {
                "ids": {
                    product_id: quantity
                }
            }

        print(f"Booking data: {json.dumps(booking_data)}")
        
        # Using the correct 'book' endpoint from documentation
        response = make_api_request(f"orders/{order_id}/book", method="POST", data=booking_data)
        if response and 'order' in response:
            return {
                "order_id": response["order"]["id"],
                "status": response["order"]["status"],
                "grand_total": response["order"].get("grand_total"),
                "payment_status": response["order"].get("payment_status")
            }
        return {"error": "Failed to book order"}
    except Exception as e:
        print(f"Error booking order: {str(e)}")
        return {"error": f"Error booking order: {str(e)}"}

# Function to execute assistant functions based on OpenAI's request
def execute_function(function_name, arguments):
    """Execute a function based on its name and arguments"""
    # Parse arguments
    args = json.loads(arguments)
    
    if function_name == "list_product_groups":
        return list_product_groups()
    
    elif function_name == "get_product_group":
        return get_product_group(args.get("product_group_id"))
    
    elif function_name == "check_availability":
        return check_availability(
            args.get("product_id"),
            args.get("from_date"),
            args.get("to_date")
        )
    
    elif function_name == "get_product_pricing":
        return get_product_pricing(args.get("product_id"))
    
    elif function_name == "create_customer":
        return create_customer(
            args.get("name"),
            args.get("email"),
            args.get("address1"),
            args.get("address2"),
            args.get("city"),
            args.get("zipcode"),
            args.get("country"),
            args.get("phone")
        )
    
    elif function_name == "create_order":
        return create_order(
            args.get("customer_id"),
            args.get("start_date"),
            args.get("end_date")
        )
    
    elif function_name == "book_order":
        return book_order(
            args.get("order_id"),
            args.get("product_id"),
            args.get("quantity", 1)
        )
    
    else:
        return {"error": f"Unknown function: {function_name}"}

# Create Assistant
def setup_assistant():
    """Get the assistant - assistant should already be configured in OpenAI"""
    client = get_openai_client()
    if not client:
        return
    
    # Simply check if the assistant exists, we don't need to update it
    try:
        assistant = client.beta.assistants.retrieve(st.session_state.assistant_id)
        print(f"Using existing assistant: {assistant.name}")
        return assistant
    except Exception as e:
        st.error(f"Error retrieving assistant: {e}")
        return None

# Process an OpenAI run
def process_run():
    client = get_openai_client()
    if not client:
        return
    
    if not st.session_state.thread_id or not st.session_state.run_id:
        return
    
    try:
        run = client.beta.threads.runs.retrieve(
            thread_id=st.session_state.thread_id,
            run_id=st.session_state.run_id
        )
        
        print(f"Run status: {run.status}")  # Terminal logging only
        
        if run.status == "requires_action":
            # Handle function calls
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                print(f"Executing function: {function_name} with args: {function_args}")  # Terminal logging only
                
                # Execute the function
                function_response = execute_function(function_name, function_args)
                
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(function_response)
                })
            
            # Submit outputs back to OpenAI
            client.beta.threads.runs.submit_tool_outputs(
                thread_id=st.session_state.thread_id,
                run_id=st.session_state.run_id,
                tool_outputs=tool_outputs
            )
            return True  # Still processing
            
        elif run.status == "completed":
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
            
        elif run.status in ["failed", "cancelled", "expired"]:
            st.error(f"Run {run.status}: {run.last_error}")
            st.session_state.run_id = None
            return False  # Processing failed
            
        else:
            # Still running
            return True
            
    except Exception as e:
        st.error(f"Error processing run: {e}")
        st.session_state.run_id = None
        return False

# Send a message to the assistant
def send_message(message):
    client = get_openai_client()
    if not client:
        return
    
    ensure_thread()
    
    # Add user message to the UI
    st.session_state.messages.append({
        "role": "user",
        "content": message,
        # No id for user messages initially
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

# Initialize the assistant when app starts
if validate_api_keys():
    setup_assistant()
    ensure_thread()

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

# Add this just before the chat input section
# Process any ongoing run
if st.session_state.run_id:
    with st.spinner("🔄 Getting information..."):
        still_running = process_run()
        if still_running:
            st.rerun()
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
    if validate_api_keys():
        send_message(user_input)
        st.rerun()