from transformers import PreTrainedTokenizerFast, GPT2LMHeadModel
import torch
import nltk
import re

nltk.download('punkt')

model_name = "dialoGPT-medium-korean-chit-chat-scratch-wikipedia"
#model_name = "dialoGPT-medium-korean-chit-chat-scratch"
#model_name = "dialoGPT-small-korean-chit-chat-scratch-newtok"
#model_checkpoint = 'byeongal/Ko-DialoGPT'
model_checkpoint = f"./Models/{model_name}/checkpoint-130000"   # restore and continue


device = 'cuda' if torch.cuda.is_available() else 'cpu'
#device = 'cpu'

print("running on", device, model_checkpoint)

tokenizer = PreTrainedTokenizerFast.from_pretrained(model_checkpoint)
model = GPT2LMHeadModel.from_pretrained(model_checkpoint).to(device)

past_user_inputs = []
generated_responses = []

max_input = 512

history = []
while True:
    print("")
    user_input = input(">> User: ")
    if user_input == 'bye':
        break;
    hist = ""
    if user_input[-1] == '/':
        history = []
    for chat in history[-3:]:
        hist += chat[0] + tokenizer.eos_token + chat[1] + tokenizer.eos_token
    hist += user_input + tokenizer.eos_token
    hist = hist[-max_input:]
    print("====", len(history))
    print("===>", hist)
    print("----")
    # encode the new user input, add the eos_token and return a tensor in Pytorch
    new_user_input_ids = tokenizer.encode(hist, return_tensors='pt').to(device)
    # print(new_user_input_ids)

    # append the new user input tokens to the chat history
    #bot_input_ids = torch.cat([chat_history_ids, new_user_input_ids], dim=-1) if step > 0 else new_user_input_ids
    bot_input_ids = new_user_input_ids

    # generated a response while limiting the total chat history to 1000 tokens, 
    chat_history_ids = model.generate(
        bot_input_ids, max_length=bot_input_ids.shape[-1] + 100,
        pad_token_id=tokenizer.eos_token_id,  
        no_repeat_ngram_size=3,       
        do_sample=True, 
        num_beams=5,
        early_stopping=True,
        repetition_penalty=2.0,
        length_penalty=0.65,
        top_k=20, 
        #top_p=0.7,
        #temperature = 0.8
    )

    bot_text = tokenizer.decode(chat_history_ids[0][bot_input_ids.shape[-1]:], skip_special_tokens=True).replace("#@??????#", "OOO")
    print("org=", bot_text)
    bot_text = re.sub("\\.\\.+", ". ", bot_text)
    bot_text = re.sub("\\!\\!+", "! ", bot_text)
    bot_text = re.sub("\\?\\?+", "? ", bot_text)
    print("remove ...=", bot_text)
    bot_text = nltk.sent_tokenize(bot_text)
    print("sentence=", bot_text)
    bot_text_temp = bot_text[0]
    if (len(bot_text_temp) < 5 and len(bot_text) > 1):
        bot_text_temp += bot_text[1]
    bot_text = bot_text_temp
    print("Bot: {}".format(bot_text))    
    history.append((user_input, bot_text))
    
    print("\nchat history---")
    for chat in history:
        print(f"User:\t{chat[0]}:\nBot:\t{chat[1]}\n")

print("\nchat history full---")
for chat in history:
    print(f"User:\t{chat[0]}:\nBot:\t{chat[1]}\n")
