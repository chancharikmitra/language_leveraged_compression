import random
from typing import Callable, Dict, List

import numpy as np
import torch
from torch.utils.data import Dataset

from virtex.data.tokenizers import SentencePieceBPETokenizer
#from virtex.data import transforms as T
from virtex.data.datasets.coco_captions import CocoCaptionsDataset
from virtex import factories

from PIL import Image
import clip

class CaptioningDataset(Dataset):
    r"""
    A dataset which provides image-caption (forward and backward) pairs from
    a COCO Captions annotation file. This is used for pretraining tasks which
    use captions - bicaptioning, forward captioning and token classification.
    Args:
        data_root: Path to dataset directory containing images and annotations.
        split: Name of COCO 2017 split to read. One of ``{"train", "val"}``.
        tokenizer: Tokenizer which maps word tokens to their integer IDs.
        image_transform: List of image transformations, from either
            `albumentations <https://albumentations.readthedocs.io/en/latest/>`_
            or :mod:`virtex.data.transforms`.
        max_caption_length: Maximum number of tokens to keep in caption tokens.
            Extra tokens will be trimmed from the right end of the token list.
    """

    def __init__(
        self,
        data_root: str,
        split: str,
        transform,
        tokenizer = factories.TokenizerFactory.create("SentencePieceBPETokenizer", "../virtex/datasets/vocab/coco_10k.model"),
        max_caption_length: int = 30
    ):
        self._dset = CocoCaptionsDataset(data_root, split)
        self.tokenizer = tokenizer
        self.transform = transform
        self.max_caption_length = max_caption_length

        # Short handles for common tokens for convenience:
        self.padding_idx = tokenizer.token_to_id("<unk>")
        self.sos_id = tokenizer.token_to_id("[SOS]")
        self.eos_id = tokenizer.token_to_id("[EOS]")

    def __len__(self):
        return len(self._dset)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:

        # keys: {"image_id", "image", "captions"}
        instance = self._dset[idx]
        image_id, image, captions = (
            instance["image_id"],
            instance["image"],
            instance["captions"],
        )
        caption = random.choice(captions)
        ''' Old Transformation for Virtex:
        # Transform image-caption pair and convert image from HWC to CHW format.
        # Pass in caption to image_transform due to paired horizontal flip.
        # Caption won't be tokenized/processed here.
        image_caption = self.image_transform(image=image, caption=caption)
        image, caption = image_caption["image"], image_caption["caption"]
        image = np.transpose(image, (2, 0, 1))
        '''
        #--------Using New Transforms for RQVAE:--------
        #With Caption Transform:
        #dirCheck = False
        #if "left" in caption or "right" in caption:
        #    print(caption)
        #    dirCheck = True
        PILimg = Image.fromarray(image)
        image, caption = self.transform((PILimg, caption))
        #if dirCheck:
        #    print(caption)
        #Without Caption Transform:
        #image = self.transform(Image.fromarray(image))
        #print("Caption Before:", caption)
        
        #CLIP Input --------------
        #tokenizer = AutoTokenizer.from_pretrained("openai/clip-vit-base-patch32")

        #CLIPInput = tokenizer(caption, padding=True, return_tensors="pt")#.to(self.device)
        text = clip.tokenize(caption)
        #model, preprocess = clip.load("ViT-B/32", device="cpu")
        #text_features = model.encode_text(text)
        #print(text)
        #print(text_features.shape)
        #------------------
        caption_tokens = [self.sos_id, *self.tokenizer.encode(caption), self.eos_id]
        caption_tokens = caption_tokens[: self.max_caption_length]
        return {
            "image_id": torch.tensor(image_id, dtype=torch.long),
            "image": image,
            "caption_tokens": torch.tensor(caption_tokens, dtype=torch.long),
            "noitpac_tokens": torch.tensor(caption_tokens, dtype=torch.long).flip(0),
            "caption_lengths": torch.tensor(len(caption_tokens), dtype=torch.long),
            "CLIP_text": text
            #"CLIP_input_ids": torch.reshape(CLIPInput["input_ids"], [-1]),
            #"CLIP_attention_mask":  torch.reshape(CLIPInput["attention_mask"], [-1])
        }

    def collate_fn(
        self, data: List[Dict[str, torch.Tensor]]
    ) -> Dict[str, torch.Tensor]:
        # Pad `caption_tokens` and `masked_labels` up to this length.
        caption_tokens = torch.nn.utils.rnn.pad_sequence(
            [d["caption_tokens"] for d in data],
            batch_first=True,
            padding_value=self.padding_idx,
        )
        noitpac_tokens = torch.nn.utils.rnn.pad_sequence(
            [d["noitpac_tokens"] for d in data],
            batch_first=True,
            padding_value=self.padding_idx,
        )
        '''CLIP_input_ids = torch.nn.utils.rnn.pad_sequence(
            [d["CLIP_input_ids"] for d in data],
            batch_first=True,
            padding_value=0
        )
        CLIP_attention_mask = torch.nn.utils.rnn.pad_sequence(
            [d["CLIP_attention_mask"] for d in data],
            batch_first=True,
            padding_value=0
        )'''
        return {
            "image_id": torch.stack([d["image_id"] for d in data], dim=0),
            "image": torch.stack([d["image"] for d in data], dim=0),
            "caption_tokens": caption_tokens,
            "noitpac_tokens": noitpac_tokens,
            "caption_lengths": torch.stack([d["caption_lengths"] for d in data]),
            "CLIP_text": torch.cat([d["CLIP_text"] for d in data], dim=0)
            #"CLIP_input_ids": CLIP_input_ids,
            #"CLIP_attention_mask": CLIP_attention_mask
        }