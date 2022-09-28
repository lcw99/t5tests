# -*- coding: utf-8 -*-
"""Training an Article Title Generation Model with T5 Korean.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1UQ5QqXGsUNIrx_GWRut2sEhsefZRXEVy

# Training an Article Title Generation Model with T5

## Install libraries and download the dataset

Load kaggle.json file.
"""

# !pip install datasets transformers rouge-score nltk
# !pip install sentencepiece

# from google.colab import drive
# drive.mount('/content/drive')

# !kaggle

# !cp kaggle.json ~/.kaggle/kaggle.json

# !kaggle datasets download -d ninedragons/korean-text-summary

"""## Load the dataset"""

import transformers
from datasets import load_dataset, load_metric

#medium_datasets = load_dataset("json", data_files="test_data.json")
medium_datasets = load_dataset("json", data_files="/home/chang/nas1/linux/dataset/text/한국어 SNS/korean_sns_training.zip")

medium_datasets

"""## Dataset train/validation/test split"""

datasets_train_test = medium_datasets["train"].train_test_split(test_size=60000)
datasets_train_validation = datasets_train_test["train"].train_test_split(test_size=30000)

medium_datasets["train"] = datasets_train_validation["train"]
medium_datasets["validation"] = datasets_train_validation["test"]
medium_datasets["test"] = datasets_train_test["test"]

medium_datasets

n_samples_train = len(medium_datasets["train"])
n_samples_validation = len(medium_datasets["validation"])
n_samples_test = len(medium_datasets["test"])
n_samples_total = n_samples_train + n_samples_validation + n_samples_test

print(f"- Training set: {n_samples_train*100/n_samples_total:.2f}%")
print(f"- Validation set: {n_samples_validation*100/n_samples_total:.2f}%")
print(f"- Test set: {n_samples_test*100/n_samples_total:.2f}%")

# keep only a subsample of the datasets
medium_datasets["train"] = medium_datasets["train"].shuffle()
#medium_datasets["train"] = medium_datasets["train"].shuffle().select(range(5000))
medium_datasets["validation"] = medium_datasets["validation"].shuffle().select(range(500))
medium_datasets["test"] = medium_datasets["test"].shuffle().select(range(500))

print(medium_datasets)

"""## Data preprocessing"""

import nltk
nltk.download('punkt')
import string
from transformers import AutoTokenizer, T5TokenizerFast

model_name = "pko-t5-base-korean-chit-chat"

#model_checkpoint = "google/mt5-base"
model_checkpoint = "paust/pko-t5-base"
#model_checkpoint = "google/byt5-base"
#model_checkpoint = "google/byt5-small"
#model_checkpoint = f"./Models/{model_name}/checkpoint-158000"   # restore and continue

model_name = "pko-t5-base-korean-chit-chat"
model_dir = f"./Models/{model_name}"

max_input_length = 512
max_target_length = 128

tokenizer = AutoTokenizer.from_pretrained(model_checkpoint)
#tokenizer = T5TokenizerFast.from_pretrained(model_checkpoint)
#tokenizer = T5TokenizerFast.from_pretrained(model_dir, local_files_only=True)
tokenizer.model_max_length = max_target_length

prefix = ""

def clean_text(text):
  sentences = nltk.sent_tokenize(text.strip())
  sentences_cleaned = [s for sent in sentences for s in sent.split("\n")]
  sentences_cleaned_no_titles = [sent for sent in sentences_cleaned
                                 if len(sent) > 0 and
                                 sent[-1] in string.punctuation]
  text_cleaned = "\n".join(sentences_cleaned_no_titles)
  return text_cleaned

def preprocess_data(examples):
  texts_cleaned = [clean_text(text) for text in examples["source"]]
  #print(texts_cleaned)
  inputs = [prefix + text for text in texts_cleaned]
  model_inputs = tokenizer(inputs, max_length=max_input_length, truncation=True)

  # Setup the tokenizer for targets
  with tokenizer.as_target_tokenizer():
    labels = tokenizer(examples["target"], max_length=max_target_length, 
                       truncation=True)

  model_inputs["labels"] = labels["input_ids"]
  return model_inputs

print("no_train_data=", len(medium_datasets["train"]))
medium_datasets_cleaned = medium_datasets.filter(lambda example: (len(example['source']) >= 5) and (len(example['target']) >= 2))
print("no_train_data(filterd)=", len(medium_datasets_cleaned["train"]))
tokenized_datasets = medium_datasets_cleaned.map(preprocess_data, batched=True)
print(tokenized_datasets)

"""## Fine-tune T5"""

from transformers import AutoModelForSeq2SeqLM, DataCollatorForSeq2Seq, Seq2SeqTrainingArguments, Seq2SeqTrainer, MT5ForConditionalGeneration

#!rm -r {model_dir}

batch_size = 8
args = Seq2SeqTrainingArguments(
    model_dir,
    evaluation_strategy="steps",
    eval_steps=1000,
    logging_strategy="steps",
    logging_steps=1000,
    save_strategy="steps",
    save_steps=2000,
    learning_rate=4e-5,
    #per_device_train_batch_size=batch_size,
    #per_device_eval_batch_size=batch_size,
    weight_decay=0.01,
    save_total_limit=30,
    num_train_epochs=1,
    predict_with_generate=True,
    fp16=False,
    load_best_model_at_end=True,
    metric_for_best_model="rouge1",
    report_to="tensorboard",
    auto_find_batch_size=True,
    #sharded_ddp="simple"
)

data_collator = DataCollatorForSeq2Seq(tokenizer)

import numpy as np

metric = load_metric("rouge")

def compute_metrics(eval_pred):
    predictions, labels = eval_pred
    decoded_preds = tokenizer.batch_decode(predictions, skip_special_tokens=True)
    
    # Replace -100 in the labels as we can't decode them.
    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
    decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
    
    # Rouge expects a newline after each sentence
    decoded_preds = ["\n".join(nltk.sent_tokenize(pred.strip()))
                      for pred in decoded_preds]
    decoded_labels = ["\n".join(nltk.sent_tokenize(label.strip())) 
                      for label in decoded_labels]
    
    # Compute ROUGE scores
    result = metric.compute(predictions=decoded_preds, references=decoded_labels,
                            use_stemmer=True)

    # Extract ROUGE f1 scores
    result = {key: value.mid.fmeasure * 100 for key, value in result.items()}
    
    # Add mean generated length to metrics
    prediction_lens = [np.count_nonzero(pred != tokenizer.pad_token_id)
                      for pred in predictions]
    result["gen_len"] = np.mean(prediction_lens)
    
    return {k: round(v, 4) for k, v in result.items()}

# Function that returns an untrained model to be trained
def model_init():
    model = AutoModelForSeq2SeqLM.from_pretrained(model_checkpoint)
    model.config.max_length = max_target_length
    return model
    #return MT5ForConditionalGeneration.from_pretrained(model_checkpoint)
    #return MT5ForConditionalGeneration.from_pretrained(model_dir, local_files_only=True)
     
trainer = Seq2SeqTrainer(
    model_init=model_init,
    args=args,
    train_dataset=tokenized_datasets["train"],
    eval_dataset=tokenized_datasets["validation"],
    data_collator=data_collator,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics
)

# Commented out IPython magic to ensure Python compatibility.
# Start TensorBoard before training to monitor it in progress
# %load_ext tensorboard
# %tensorboard --logdir '{model_dir}'/runs

trainer.train()

trainer.save_model()

"""## Load the model from GDrive"""

tokenizer = AutoTokenizer.from_pretrained(model_dir)
model = AutoModelForSeq2SeqLM.from_pretrained(model_dir)

max_input_length = 512

text = """
We define access to a Streamlit app in a browser tab as a session.
For each browser tab that connects to the Streamlit server, a new session is created.
Streamlit reruns your script from top to bottom every time you interact with your app.
Each reruns takes place in a blank slate: no variables are shared between runs.
Session State is a way to share variables between reruns, for each user session.
In addition to the ability to store and persist state, Streamlit also exposes the
ability to manipulate state using Callbacks. In this guide, we will illustrate the
usage of Session State and Callbacks as we build a stateful Counter app.
For details on the Session State and Callbacks API, please refer to our Session
State API Reference Guide. Also, check out this Session State basics tutorial
video by Streamlit Developer Advocate Dr. Marisa Smith to get started:
"""

inputs = [prefix + text]

inputs = tokenizer(inputs, max_length=max_input_length, truncation=True, return_tensors="pt")
output = model.generate(**inputs, num_beams=8, do_sample=True, min_length=10, max_length=100)
decoded_output = tokenizer.batch_decode(output, skip_special_tokens=True)[0]
predicted_title = nltk.sent_tokenize(decoded_output.strip())[0]

print(predicted_title)
