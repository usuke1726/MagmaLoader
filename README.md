
# Magma Loader

`load`構文を持つMagmaコードをコピペしてMagma Calculatorで実行するためのPythonスクリプト．

## 実行方法

`python3 main.py [-h] [-c] [-n] [-p] <file-name>`

### オプション

- `-c` (`--leave-comments`): コメント文を消去しない
- `-p` (`--stdout`): 標準出力を用いる(これを指定しない場合，`pyperclip`を用いてクリップボードにコピーします)
- `-n` (`--no-trim`): 出力コードのトリミングを行わない
- `-s` (`--send`): Magmaスクリプトを直接実行する(実験段階)

## 注意

- `load`構文は行頭に書いてください．
    - 半角スペースやタブ文字以外の文字が前にある場合，適切にファイルが読み込まれません．

