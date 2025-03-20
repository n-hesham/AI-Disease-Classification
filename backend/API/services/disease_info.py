import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

def get_disease_info(disease_name: str) -> str:
    """Get medical information using GPT-4"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a professional medical assistant"},
                {"role": "user", "content": f"""
                    Provide detailed information about {disease_name} including:
                    1. Definition
                    2. Common Symptoms
                    3. Causes
                    4. Prevention Methods
                    5. Recommended Treatments
                    6. When to see a doctor
                    Use clear medical terminology and structured format.
                """}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
        
    except Exception as e:
        raise RuntimeError(f"OpenAI API Error: {str(e)}")