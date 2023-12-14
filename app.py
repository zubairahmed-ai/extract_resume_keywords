from fastapi import FastAPI, HTTPException, Query, WebSocket
import fitz  # PyMuPDF library for handling PDF files
from fastapi.responses import HTMLResponse
import os 
import uvicorn
import datetime, json

app = FastAPI(swagger_ui_parameters={"syntaxHighlight": True})
from langchain.llms import OpenAI
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.prompts import ChatPromptTemplate, HumanMessagePromptTemplate
from langchain.chains import LLMChain
import os
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.output_parsers import OutputFixingParser
from langchain.schema import OutputParserException
os.environ["OPENAI_API_KEY"] = "<your openai api key>"
llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0.9)

response_schemas = [
    ResponseSchema(name="firstname", description="First name"),
    ResponseSchema(name="lastname", description="Last name"),
    ResponseSchema(name="email", description="Email"),
    ResponseSchema(name="phonenumber", description="Phone number"),
    ResponseSchema(name="skillset", description="Skill set"),
    ResponseSchema(name="Experience", description="Experience"),
    ResponseSchema(name="education", description="Education"),
    ResponseSchema(name="social", description="Social media")
    
]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
format_instructions = output_parser.get_format_instructions()
prompt_msgs = [
        SystemMessage(
            content="You are also a world class algorithm for extracting information from resumes in a structured format, the resumes can be any format, get only the top level skill set, in the 'experience' extract month and year only and highlights of the experience of the last company that the person has worked for, in the 'education' extract only extract the most recent degree title and it's year, if any of the requested information is not present in the given resume below and you don't know the answer, say 'N/A'. Do not create an answer yourself."
        ),        
        HumanMessagePromptTemplate.from_template("format_instructions: {format_instructions}"),
        HumanMessagePromptTemplate.from_template("context: {context}"),
        HumanMessagePromptTemplate.from_template("{input}"),

]
prompt = ChatPromptTemplate(messages=prompt_msgs, input_variables=["context","input"], partial_variables={"format_instructions": format_instructions})
chain = LLMChain(llm=llm, prompt=prompt)
model = OpenAI(temperature=0, max_tokens=2000)
def extract_resume_data(resume: str):
    start_time = datetime.datetime.now()

    context = resume
    _input = prompt.format_prompt(context=context, input="Extract the first name, last name, email, phone number, skill set, experience, education, social media links")
    output = model(_input.to_string())
    output_stripped = output
   
    extracted_data_json = output_stripped
    try:        
        response = output_parser.parse(extracted_data_json)    
    except:
        new_parser = OutputFixingParser.from_llm(
            parser=output_parser,
            llm=ChatOpenAI()
        )
        response = new_parser.parse(extracted_data_json)
    end_time = datetime.datetime.now()
    difference = end_time - start_time
    timediff = {"timetaken": difference.seconds}
    response.update(timediff)

    return response


def convert_pdf_to_text(file_path):
    try:        
        with fitz.open(file_path) as pdf_document:
            text = ""            
            for page_number in range(pdf_document.page_count):
                page = pdf_document[page_number]
                text += page.get_text()                         
            
            extracted_data_json = extract_resume_data(text)
            
            return extracted_data_json
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error converting PDF to text: {str(e)}")
html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/convert_resume");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(html)

@app.websocket("/convert_resume")
# async def convert_resume(file_name: str = Query(..., description="Name of the PDF resume file")):
async def convert_resume(websocket: WebSocket):
    try:
        await websocket.accept()
        while True:
            file_name = await websocket.receive_text()
            # Assuming the PDF resumes are stored in a specific directory
            resumes_directory = "pdf"
            file_path = f"{resumes_directory}/{file_name}"

            # Convert the PDF file to text
            text_content = convert_pdf_to_text(file_path)

            await websocket.send_text(f"Message text was: {text_content}")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing the file: {str(e)}")

@app.get("/convert_resume")
# async def convert_resume(file_name: str = Query(..., description="Name of the PDF resume file")):
async def convert_resume(file_name: str = Query(..., description="Name of the PDF resume file")):
    try:
        # Assuming the PDF resumes are stored in a specific directory
        resumes_directory = "pdf"

        file_path = f"{resumes_directory}/{file_name}"

        # Convert the PDF file to text
        text_content = convert_pdf_to_text(file_path)

        return {"text_content": text_content}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing the file: {str(e)}")

if __name__ == "__main__":
    # Run the FastAPI application using uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
    # uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)