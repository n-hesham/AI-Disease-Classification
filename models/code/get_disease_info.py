import openai
import os

# Load API Key from environment variables (best practice for security)
openai.api_key = "your-api-key-here"

def get_disease_info(disease_name):
    """
    Uses ChatGPT API to retrieve information about a skin disease.
    
    Args:
        disease_name (str): Name of the disease to retrieve information about.

    Returns:
        str: Detailed medical information including causes, symptoms, and when to see a doctor.
    """
    prompt = f"Provide detailed medical information about {disease_name}, including causes, symptoms, and when to consult a doctor."

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Use "gpt-4" or "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "You are a medical assistant providing accurate health information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=350,
            temperature=0.6
        )
        return response["choices"][0]["message"]["content"]
    
    except Exception as e:
        return f"Error retrieving information: {str(e)}"

# Optional: Test the function
if __name__ == "__main__":
    print(get_disease_info("Psoriasis"))
