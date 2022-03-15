# 来源 https://github.com/OS984/DiscordBotBackend/blob/3b06b8be39e4dbc07722b0afefeee4c18c136102/NeuralTTS.py
# A completely innocent attempt to borrow proprietary Microsoft technology for a much better TTS experience
import requests
import websockets
import asyncio
from datetime import datetime
import time
import re
import uuid
import argparse
import asyncio
import requests
from flask import Flask, request, send_from_directory

'''命令行参数解析'''
def parseArgs():
    parser = argparse.ArgumentParser(description='text2speech')
    parser.add_argument('--input', dest='input', help='SSML(语音合成标记语言)的路径', type=str, required=True)
    parser.add_argument('--output', dest='output', help='保存mp3文件的路径', type=str, required=False)
    args = parser.parse_args()
    return args

# Fix the time to match Americanisms
def hr_cr(hr):
    corrected = (hr - 1) % 24
    return str(corrected)

# Add zeros in the right places i.e 22:1:5 -> 22:01:05
def fr(input_string):
    corr = ''
    i = 2 - len(input_string)
    while (i > 0):
        corr += '0'
        i -= 1
    return corr + input_string

# Generate X-Timestamp all correctly formatted
def getXTime():
    now = datetime.now()
    return fr(str(now.year)) + '-' + fr(str(now.month)) + '-' + fr(str(now.day)) + 'T' + fr(hr_cr(int(now.hour))) + ':' + fr(str(now.minute)) + ':' + fr(str(now.second)) + '.' + str(now.microsecond)[:3] + 'Z'

# Async function for actually communicating with the websocket
async def transferMsTTSData(SSML_text, outputPath):
    endpoint1 = "https://azure.microsoft.com/en-gb/services/cognitive-services/text-to-speech/"
    r = requests.get(endpoint1)
    main_web_content = r.text
    # They hid the Auth key assignment for the websocket in the main body of the webpage....
    token_expr = re.compile('token: \"(.*?)\"', re.DOTALL)
    Auth_Token = re.findall(token_expr, main_web_content)[0]
    # req_id = str('%032x' % random.getrandbits(128)).upper()
    # req_id is generated by uuid.
    req_id = uuid.uuid4().hex.upper()
    print(req_id)
    endpoint2 = "wss://eastus.tts.speech.microsoft.com/cognitiveservices/websocket/v1?Authorization=" + \
        Auth_Token + "&X-ConnectionId=" + req_id
    async with websockets.connect(endpoint2) as websocket:
        payload_1 = '{"context":{"system":{"name":"SpeechSDK","version":"1.12.1-rc.1","build":"JavaScript","lang":"JavaScript","os":{"platform":"Browser/Linux x86_64","name":"Mozilla/5.0 (X11; Linux x86_64; rv:78.0) Gecko/20100101 Firefox/78.0","version":"5.0 (X11)"}}}}'
        message_1 = 'Path : speech.config\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/json\r\n\r\n' + payload_1
        await websocket.send(message_1)

        payload_2 = '{"synthesis":{"audio":{"metadataOptions":{"sentenceBoundaryEnabled":false,"wordBoundaryEnabled":false},"outputFormat":"audio-16khz-32kbitrate-mono-mp3"}}}'
        message_2 = 'Path : synthesis.context\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/json\r\n\r\n' + payload_2
        await websocket.send(message_2)

        # payload_3 = '<speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US"><voice name="' + voice + '"><mstts:express-as style="General"><prosody rate="'+spd+'%" pitch="'+ptc+'%">'+ msg_content +'</prosody></mstts:express-as></voice></speak>'
        payload_3 = SSML_text
        message_3 = 'Path: ssml\r\nX-RequestId: ' + req_id + '\r\nX-Timestamp: ' + \
            getXTime() + '\r\nContent-Type: application/ssml+xml\r\n\r\n' + payload_3
        await websocket.send(message_3)

        # Checks for close connection message
        end_resp_pat = re.compile('Path:turn.end')
        audio_stream = b''
        while(True):
            response = await websocket.recv()
            print('receiving...')
            # Make sure the message isn't telling us to stop
            if (re.search(end_resp_pat, str(response)) == None):
                # Check if our response is text data or the audio bytes
                if type(response) == type(bytes()):
                    # Extract binary data
                    try:
                        start_ind = str(response).find('Path:audio')
                        #audio_string += str(response)[start_ind+14:-1]
                        audio_stream += response[start_ind-2:]
                    except:
                        pass
            else:
                break
        with open(f'{outputPath}.mp3', 'wb') as audio_out:
            audio_out.write(audio_stream)


async def mainSeq(SSML_text, outputPath):
    await transferMsTTSData(SSML_text, outputPath)

def get_SSML(path):
    with open(path,'r',encoding='utf-8') as f:
        return f.read()

def make_SSML(text):
    return '''
    <speak xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="http://www.w3.org/2001/mstts" xmlns:emo="http://www.w3.org/2009/10/emotionml" version="1.0" xml:lang="en-US">
        <voice name="zh-CN-XiaoxiaoNeural">
            <prosody rate="0%" pitch="0%">
            {}
            </prosody>
        </voice>
    </speak>
    '''.format(text)


async def main(text):
    SSML_text = make_SSML(text)
    output_path = 'output_' + str(int(time.time() * 1000))
    await mainSeq(SSML_text, output_path)
    try:
        return send_from_directory('',output_path+".mp3")
    except Exception as e:
        return str(e)

app = Flask(__name__)

@app.route("/")
def index():
    if 'text' in request.args.keys():
        arg = request.args.get("text")

        responses = asyncio.run(main(arg))
        return responses
    else:
        return 'hello'


if __name__ == "__main__":
    app.run(debug=False, use_reloader=False)
# if __name__ == "__main__":
#     args = parseArgs()
#     SSML_text = get_SSML(args.input)
#     output_path = args.output if args.output else 'output_'+ str(int(time.time()*1000))
#     asyncio.get_event_loop().run_until_complete(mainSeq(SSML_text, output_path))
#     print('completed')
#     # python tts.py --input SSML.xml
#     # python tts.py --input SSML.xml --output 保存文件名