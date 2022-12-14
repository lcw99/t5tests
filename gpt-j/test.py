import os, glob
import transformers
import torch
#from gpt_j_8bit import GPTJBlock8, GPTJForCausalLM8, GPTJModel8, add_adapters
from transformers import AutoTokenizer, logging, pipeline, AutoModel
import argparse, evaluate
from datasets import load_dataset, load_from_disk 

pipe = True

model_name = "GPT-j-6B-8bit-wikipedia-finetune"
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

parser = argparse.ArgumentParser()
parser.add_argument("-m", "--model", help = "model name")
parser.add_argument("-l", "--local_model", help = "local model name")
parser.add_argument("-t", "--tokenizer", help = "tokenizer")
parser.add_argument("-p", "--path", help = "model path with tokenizer")
args = parser.parse_args()
latest_model_dir = "none"
if args.local_model:
    print("=== param using local model", args.local_model)
    model_name = args.local_model
    model_dir = f"./Models/{model_name}"
    try:
        latest_model_dir = max(glob.glob(os.path.join(model_dir, 'checkpoint-*/')), key=os.path.getmtime)
        tokenizer_dir = latest_model_dir
    except:
        latest_model_dir = model_dir
if args.model:
    print("=== param model name", args.model)
    model_name = args.model
    latest_model_dir = model_name
    if model_name == "hivemind/gpt-j-6B-8bit":
        tokenizer_dir = "EleutherAI/gpt-j-6B"
    else:
        tokenizer_dir = latest_model_dir
if args.tokenizer:
    tokenizer_dir = args.tokenizer
    
if args.path:
    latest_model_dir = args.path
    tokenizer_dir = latest_model_dir

print("\n---------------------------")
print("model dir =\t", latest_model_dir)
print("tokenizer dir =\t", tokenizer_dir)
print("---------------------------\n")

logging.set_verbosity_error()

tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)
gpt = AutoModel.from_pretrained(
    latest_model_dir,
    torch_dtype=torch.float16,
    #low_cpu_mem_usage=True,
    # device_map='auto',
    # load_in_8bit=True,
).to(device)

text_generation = pipeline(
    "text-generation",
    model=latest_model_dir,
    tokenizer=tokenizer,
    device=0
)

perplexity = evaluate.load("perplexity", module_type="metric")
#data = load_dataset("lcw99/oscar-ko-only", split='train[:50]')
#data.save_to_disk("./test_data")
data = load_from_disk("./test_data")['text']

#data = load_dataset("lcw99/oscar-ko-only")['train']['text'][:50]
input_texts = [s[:1024] for s in data if s!='']

result = perplexity.compute(model_id=latest_model_dir, predictions=input_texts)
print(result)
#gpt.save_pretrained("./Models/gpt-j-6B-org-to-8bit-conv")

while True:
    print("\n")
    text = input("Input: ")
    if pipe:
        generated = text_generation(
            text,
            max_length=300,
            do_sample=True,
            min_length=100,
            num_return_sequences=3,
            # top_p=0.95,
            # top_k=50
        )
        print("\n")
        print(*generated, sep="\n\n")
    else:
        encoded_input = tokenizer(text, return_tensors='pt').to(device)
        print(encoded_input)
        output_sequences = gpt.generate(encoded_input["input_ids"], max_length=500)
        print(output_sequences)
        generated = tokenizer.decode(output_sequences[0], skip_special_tokens=True)        
        print(generated)