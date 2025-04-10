def handle_required_actions(self, thread_id, run_id, function_executor):
        """
        Handle any required actions for the run.
        
        Args:
            thread_id: The thread ID
            run_id: The run ID
            function_executor: A function that takes (function_name, arguments) and returns a result
        """
        try:
            logger.info(f"Retrieving run details for thread {thread_id}, run {run_id}")
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            if run.status != "requires_action":
                logger.info(f"No actions required. Run status: {run.status}")
                return False
            
            tool_outputs = []
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            
            logger.info(f"Found {len(tool_calls)} tool calls to execute")
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                logger.info(f"Executing function: {function_name}")
                logger.debug(f"Function arguments: {function_args}")
                
                # Execute the function through the provided executor
                try:
                    logger.info(f"Calling function executor for {function_name}")
                    result = function_executor(function_name, function_args)
                    logger.debug(f"Function result: {json.dumps(result, indent=2)}")
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(result)
                    })
                except Exception as func_error:
                    logger.error(f"Error executing function {function_name}: {func_error}", exc_info=True)
                    # Return an error result
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps({"error": str(func_error)})
                    })
            
            # Submit the outputs back to the assistant
            logger.info(f"Submitting {len(tool_outputs)} tool outputs back to OpenAI")
            self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
            logger.info("Tool outputs submitted successfully")
            
            return True
        except Exception as e:
            logger.error(f"Error handling required actions: {e}", exc_info=True)
            raise

from openai import OpenAI
import os
import json
import logging

logger = logging.getLogger(__name__)

class AssistantManager:
    """
    Class to handle the creation and management of an OpenAI Assistant.
    Created as a singleton to ensure only one instance exists.
    """
    # Class variable to store the single instance
    _instance = None
    
    def __new__(cls, api_key=None):
        """Singleton pattern implementation to ensure only one instance exists."""
        if cls._instance is None:
            cls._instance = super(AssistantManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, api_key=None):
        """Initialize the manager with the OpenAI API key."""
        # Only initialize once
        if self._initialized:
            return
            
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required. Set it in .env or pass as parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.assistant_id = None
        self._initialized = True
    
    def create_assistant(self, name="Equipment Rental Assistant", model="gpt-4o"):
        """Create a new assistant with the specified tools and instructions."""
        
        logger.info(f"Creating new assistant: {name} with model {model}")
        
        # Define function tools for the assistant
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_product_groups",
                    "description": "Get a list of all available product groups/equipment categories",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_product_details",
                    "description": "Get details about a specific product group including availability for dates and pricing information",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "product_group_id": {
                                "type": "string",
                                "description": "The ID of the product group to check"
                            },
                            "from_date": {
                                "type": "string",
                                "description": "Start date of the rental period in YYYY-MM-DD format"
                            },
                            "to_date": {
                                "type": "string",
                                "description": "End date of the rental period in YYYY-MM-DD format"
                            }
                        },
                        "required": ["product_group_id", "from_date", "to_date"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_reservation",
                    "description": "Create a complete reservation including customer profile, order, and booking",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "customer_info": {
                                "type": "object",
                                "description": "Customer information",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Full name of the customer"
                                    },
                                    "email": {
                                        "type": "string",
                                        "description": "Email address of the customer"
                                    },
                                    "phone": {
                                        "type": "string",
                                        "description": "Phone number of the customer"
                                    },
                                    "address1": {
                                        "type": "string",
                                        "description": "Street address line 1"
                                    },
                                    "address2": {
                                        "type": "string",
                                        "description": "Street address line 2"
                                    },
                                    "city": {
                                        "type": "string",
                                        "description": "City"
                                    },
                                    "zipcode": {
                                        "type": "string",
                                        "description": "Postal/Zip code"
                                    },
                                    "country": {
                                        "type": "string",
                                        "description": "Country"
                                    }
                                },
                                "required": ["name", "email", "phone"]
                            },
                            "product_id": {
                                "type": "string",
                                "description": "The ID of the product to book"
                            },
                            "start_date": {
                                "type": "string",
                                "description": "Start date of the rental period in YYYY-MM-DD format"
                            },
                            "end_date": {
                                "type": "string",
                                "description": "End date of the rental period in YYYY-MM-DD format"
                            },
                            "quantity": {
                                "type": "integer",
                                "description": "Number of units to book",
                                "default": 1
                            }
                        },
                        "required": ["customer_info", "product_id", "start_date", "end_date"]
                    }
                }
            }
        ]
        
        logger.debug("Tools defined for assistant")
        
        # Define assistant instructions
        instructions = """
You are an Equipment Rental Specialist at Prevail Equipments. The company specializes in renting out high-quality heavy construction machinery for projects of all sizes.

WORKFLOW:
1. Ask the customer what equipment they're looking for
2. Call list_product_groups() to get available options
3. Help the customer select equipment and provide dates
4. Call get_product_details() to check availability and pricing
5. If the equipment is available, confirm details and ask customer for their information
6. Call create_reservation() to complete the booking

GUIDELINES:
- Keep responses friendly and professional
- Present equipment options clearly
- Always verify dates and provide total pricing
- Collect complete customer information before booking
- Confirm all details before making the final reservation
- If equipment is unavailable, suggest alternative dates

Your goal is to make the equipment rental process smooth and efficient.
        """
        
        # Create the assistant
        try:
            logger.info("Making API call to create assistant")
            assistant = self.client.beta.assistants.create(
                name=name,
                instructions=instructions,
                tools=tools,
                model=model
            )
            self.assistant_id = assistant.id
            logger.info(f"Successfully created assistant with ID: {self.assistant_id}")
            return self.assistant_id
        except Exception as e:
            logger.error(f"Error creating assistant: {e}", exc_info=True)
            raise
    
    def get_or_create_assistant(self, name="Equipment Rental Assistant", model="gpt-4o"):
        """
        Get an existing assistant or create a new one if it doesn't exist.
        Will first try to load from a saved file, then try to create a new one.
        """
        try:
            # Try to load saved assistant ID from file
            if os.path.exists("assistant_id.txt"):
                with open("assistant_id.txt", "r") as f:
                    self.assistant_id = f.read().strip()
                
                logger.info(f"Found saved assistant ID: {self.assistant_id}")
                
                # Verify the assistant exists
                try:
                    logger.info("Retrieving assistant details from OpenAI")
                    assistant = self.client.beta.assistants.retrieve(self.assistant_id)
                    logger.info(f"Using existing assistant: {assistant.name} (ID: {self.assistant_id})")
                    return self.assistant_id
                except Exception as e:
                    logger.warning(f"Saved assistant ID invalid: {e}")
                    logger.info("Creating new assistant")
                    self.assistant_id = None
            else:
                logger.info("No saved assistant ID found")
            
            # Create a new assistant if none exists
            if not self.assistant_id:
                self.assistant_id = self.create_assistant(name, model)
                logger.info(f"Saving assistant ID to file: {self.assistant_id}")
                # Save assistant ID to file
                with open("assistant_id.txt", "w") as f:
                    f.write(self.assistant_id)
                
            return self.assistant_id
            
        except Exception as e:
            logger.error(f"Error in get_or_create_assistant: {e}", exc_info=True)
            raise
    
    def create_thread(self):
        """Create a new conversation thread."""
        try:
            thread = self.client.beta.threads.create()
            return thread.id
        except Exception as e:
            print(f"Error creating thread: {e}")
            raise
    
    def add_message_to_thread(self, thread_id, content, role="user"):
        """Add a message to a thread."""
        try:
            message = self.client.beta.threads.messages.create(
                thread_id=thread_id,
                role=role,
                content=content
            )
            return message.id
        except Exception as e:
            print(f"Error adding message: {e}")
            raise
    
    def run_assistant(self, thread_id):
        """Run the assistant on a thread."""
        if not self.assistant_id:
            raise ValueError("No assistant ID available. Create an assistant first.")
        
        try:
            run = self.client.beta.threads.runs.create(
                thread_id=thread_id,
                assistant_id=self.assistant_id
            )
            return run.id
        except Exception as e:
            print(f"Error running assistant: {e}")
            raise
    
    def get_run_status(self, thread_id, run_id):
        """Get the status of a run."""
        try:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            return run.status
        except Exception as e:
            print(f"Error getting run status: {e}")
            raise
    
    def get_thread_messages(self, thread_id, order="asc", after=None):
        """Get messages from a thread."""
        try:
            params = {"order": order}
            if after:
                params["after"] = after
                
            messages = self.client.beta.threads.messages.list(
                thread_id=thread_id,
                **params
            )
            return messages.data
        except Exception as e:
            print(f"Error getting messages: {e}")
            raise
    
    def handle_required_actions(self, thread_id, run_id, function_executor):
        """
        Handle any required actions for the run.
        
        Args:
            thread_id: The thread ID
            run_id: The run ID
            function_executor: A function that takes (function_name, arguments) and returns a result
        """
        try:
            run = self.client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run_id
            )
            
            if run.status != "requires_action":
                return False
            
            tool_outputs = []
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                # Execute the function through the provided executor
                result = function_executor(function_name, function_args)
                
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": json.dumps(result)
                })
            
            # Submit the outputs back to the assistant
            self.client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run_id,
                tool_outputs=tool_outputs
            )
            
            return True
        except Exception as e:
            print(f"Error handling required actions: {e}")
            raise