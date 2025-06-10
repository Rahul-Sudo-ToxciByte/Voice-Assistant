import asyncio
import logging
from main import JarvisAssistant

async def test_openai():
    """Test OpenAI functionality"""
    assistant = JarvisAssistant()
    try:
        # Test chat completion
        response = await assistant.openai.get_chat_response([
            {"role": "user", "content": "Hello Jarvis, are you online?"}
        ])
        print("\nOpenAI Chat Test:")
        print(f"Response: {response}")

        # Test text analysis
        text = "I'm really excited about testing the new features!"
        analysis = await assistant.openai.analyze_sentiment(text)
        print("\nSentiment Analysis Test:")
        print(f"Analysis: {analysis['analysis']}")

        # Test summarization
        long_text = """
        Artificial intelligence (AI) is intelligence demonstrated by machines, as opposed to natural 
        intelligence displayed by animals including humans. AI research has been defined as the field 
        of study of intelligent agents, which refers to any system that perceives its environment and 
        takes actions that maximize its chance of achieving its goals. The term "artificial intelligence" 
        had previously been used to describe machines that mimic and display "human" cognitive skills 
        that are associated with the human mind, such as "learning" and "problem-solving".
        """
        summary = await assistant.openai.summarize_text(long_text)
        print("\nSummarization Test:")
        print(f"Summary: {summary}")

    except Exception as e:
        print(f"Error during OpenAI tests: {str(e)}")
    finally:
        await assistant.stop()

async def test_gmail():
    """Test Gmail functionality"""
    assistant = JarvisAssistant()
    try:
        # Test reading emails
        emails = assistant.gmail.read_emails(max_results=5)
        print("\nGmail Test:")
        print(f"Found {len(emails)} recent emails")
        
        if emails:
            print("\nMost recent email:")
            print(f"From: {emails[0]['sender']}")
            print(f"Subject: {emails[0]['subject']}")
            print(f"Date: {emails[0]['date']}")

    except Exception as e:
        print(f"Error during Gmail tests: {str(e)}")
    finally:
        await assistant.stop()

async def test_voice_commands():
    """Test voice command system"""
    assistant = JarvisAssistant()
    try:
        print("\nVoice Command System Test:")
        print("Testing command registration...")
        
        # Test a simple command
        test_command = "test command"
        test_response = "Test successful"
        
        def test_handler(params):
            return test_response
        
        assistant.voice_system.register_command(test_command, test_handler)
        print(f"Registered command: {test_command}")
        
        # Test command handling
        response = await assistant.voice_system.handle_command(test_command, {})
        print(f"Command response: {response}")

    except Exception as e:
        print(f"Error during voice command tests: {str(e)}")
    finally:
        await assistant.stop()

async def main():
    """Run all tests"""
    print("Starting Jarvis Assistant Tests...")
    
    # Test OpenAI functionality
    await test_openai()
    
    # Test Gmail functionality
    await test_gmail()
    
    # Test voice command system
    await test_voice_commands()
    
    print("\nAll tests completed!")

if __name__ == "__main__":
    asyncio.run(main()) 