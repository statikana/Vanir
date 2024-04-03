[![DigitalOcean Referral Badge](https://web-platforms.sfo2.cdn.digitaloceanspaces.com/WWW/Badge%201.svg)](https://www.digitalocean.com/?refcode=673b6b52cb2d&utm_campaign=Referral_Invite&utm_medium=Referral_Program&utm_source=badge)

Another Discord bot. I intend to make this one full of things are new to me. Code is under MIT License.


## Running your own instance

Running your own instance has a few steps but is faily straightforward.

### env
Create a file called `env.py` in `src/`, in the structure of `src/env_example.py`, with every `...` replaced
with the appropriate info.


### docker
To utilize the code module, there must be a [`Piston`](https://github.com/engineer-man/piston) API
docker container running on `localhost:2000` upon startup. Use `\dev piston <package_name> [<version> | all = all]`
to install a package, or `\dev piston` for all available and installed packages.

### Literally any dataset of words
This bot relies on a dataset of words to use for the `autocorrect` command. See `https://norvig.com/big.txt` for
the dataset normally used. Place yours in `src/dataset.txt` and it will be loaded in on startup.
(separate words by spaces or newlines)

### NLTK
There are a few NLTK external libraries that need to be downloaded using:
```python
import nltk

nltk.download("asset")
```
Just use `\pos <literally any sentence>` and, if it isn't installed properly, the errors will tell you exactly what you are 
missing and how to install it.

### requirements
See `./requirements.txt` for an updated list of required python libraries. If you cloned the repo, use 
`pip install -r requirements.txt` to install all requirements.


### NEEDS PYTHON 3.12 OR GREATER
This is for embedded f-string quotations, ie.:
```python
f"{"a" + "b"}"  # valid syntax 3.12 and greater
```

### execute main.py
Use python>=3.12 to execute `main.py`