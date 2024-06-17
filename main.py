
import os
from sys import stderr
import re
import argparse
import codecs
from glob import glob

parser = argparse.ArgumentParser()
parser.add_argument('filename', type = str)
parser.add_argument('-c', '--leave-comments', action = 'store_true', help = 'Magmaスクリプト内のコメントアウト(/* ... */ や // ...)を除外しない')
parser.add_argument('-n', '--no-trim', action = 'store_true', help = 'コメントアウト以外の文字数削減処理を一切行わない (現時点では代入演算子 := の前後スペースの省く処理のみ)')
parser.add_argument('-p', '--stdout', action = 'store_true', help = '外部ライブラリ pyperclip を使わずに結果を標準出力に渡すようにする')
parser.add_argument('-s', '--send', action = 'store_true', help = 'スクリプトを送信する')
parser.add_argument('--rel', '--use-relative-mode', action = 'store_true', help = '相対パスモード("@/"から始まるパス)を有効化する')
args = parser.parse_args()

if not args.stdout and not args.send:
    try:
        from pyperclip import copy as copy_to_clipboard
    except ImportError:
        print("pyperclip モジュールがインストールされていません．\n\n  pip install pyperclip\n\nを実行してインストールしてください．", file = stderr)
        exit(1)
if args.send:
    try:
        import requests
        from bs4 import BeautifulSoup
        import lxml
    except ImportError:
        print("requests, beautifulsoup4, lxml モジュールがインストールされていません．", file = stderr)
        exit(1)

def join_path(base_path: str, filename: str):
    if os.path.isabs(filename):
        return filename
    return os.path.abspath(
        os.path.join(
            os.path.dirname(base_path),
            filename
        )
    )

use_rel = args.rel
def load_recursively(base_path: str, path: str, depth: int = 0):
    if depth > 50:
        raise Exception("読み込み階層が深すぎます．循環参照の可能性があります．")
    try:
        with codecs.open(path, 'r', 'utf-8') as f:
            body = "\n".join([s.strip() for s in f.readlines() if s.strip()])
    except Exception as e:
        raise Exception(f"ファイル {path} の読み込みに失敗しました")
    space_patttern = "[ \t\n]"
    head_pattern = f"(^|(?<=\n))({space_patttern}*)"
    tail_pattern = f"{space_patttern}*(;|$)"
    pattern = f"{head_pattern}(load{space_patttern}+\"([^;,|*?\"<>\t\n]+)\"{tail_pattern}{space_patttern}*)+"
    matched_objects = list(re.finditer(pattern, body))

    last_index = 0
    split_bodies = []
    for m in matched_objects:
        s = m.start()
        e = m.end()
        split_bodies.append(body[last_index : s])
        split_bodies.append(body[s : e])
        last_index = e
    split_bodies.append(body[last_index:])
    for i in range(1, len(split_bodies), 2):
        filenames = [
            m[ m.find('"')+1 : m.rfind('"') ]
            for m in matched_objects[(i-1)//2].group().split(";")
            if m.strip()
        ]
        loaded_contents = []
        for filename in filenames:
            if filename.startswith("@/"):
                if not use_rel:
                    raise Exception(f"相対パスモードを使用していますが，コマンドラインオプションで有効化されていません．\nパス: {filename} ({path})\n\nコマンドラインオプション --rel を追加して有効化してください．")
                filename = filename[2:]
                load_path = join_path(path, filename)
                error_mes = f"※ @モードを使用しています．loadで読み込むファイルは，{path} から見た相対パスになっていますか？"
            else:
                load_path = join_path(base_path, filename)
                error_mes = f"※ loadで読み込むファイルは，{base_path} から見た相対パスであることに注意！"
            if os.path.exists(load_path) and os.path.isfile(load_path):
                loaded_contents.append(load_recursively(base_path, load_path, depth + 1))
            else:
                raise Exception(f"ファイル {load_path} が見つかりません\n{error_mes}")
        split_bodies[i] = "\n" + "\n".join(loaded_contents) + "\n"
    return "".join(split_bodies)

def load(filename: str):
    matched = glob(filename)
    if len(matched) == 0:
        exts = [".m", ".mg", ".magma"]
        matched = sum([glob(filename + ext) for ext in exts], [])
    if len(matched) > 1:
        raise Exception(f"マッチするファイルが多すぎます: {matched}")
    elif len(matched) == 0:
        raise Exception(f"ファイル {filename} が見つかりません")
    base_path = os.path.abspath(matched[0])
    return load_recursively(base_path, base_path)

def remove_comments(contents: str):
    lines = contents.split("\n")
    res = []
    in_comment = False
    for i in range(len(lines)):
        line = lines[i]
        if in_comment:
            if closing_block_comment_matched := re.match(r'.*\*/(.*)', line):
                in_comment = False
                line = closing_block_comment_matched.group(1)
            else:
                continue
        while block_comment_in_one_line_matched := re.match(r' */\*.*\*/(.*)', line):
            line = block_comment_in_one_line_matched.group(1)
        if opening_block_comment_matched := re.match(r' */\*', line):
            in_comment = True
            continue
        if inline_comment_matched := re.match(r' *//', line):
            continue
        if line.strip():
            res.append(line)
    return "\n".join(res)

def remove_spaces_around_assignment_operators(contents: str):
    lines = contents.split("\n")
    res = []
    for i in range(len(lines)):
        line = lines[i]
        pattern = r'^([^\'"]*?)( +:= *| *:= +)(.*?)$'
        while matched := re.match(pattern, line):
            line = matched[1] + ":=" + matched[3]
        res.append(line)
    return "\n".join(res)

def send_and_print_result(contents: str):
    url = "http://magma.maths.usyd.edu.au/xml/calculator.xml"
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    data = {'input': contents}
    print("送信中...", file = stderr)
    try:
        res = requests.post(url, data = data, headers = headers, timeout=(15.0, 120.0))
    except requests.exceptions.Timeout as e:
        print("タイムアウトが発生しました．", file = stderr)
        exit(2)
    except Exception as e:
        print(f"エラーが発生しました\n{e}\n", file = stderr)
        exit(1)
    soup = BeautifulSoup(res.text, 'lxml-xml')
    warnings = soup.select('warning')
    errored = len(warnings) > 0
    if errored:
        print("*** エラー ***", file = stderr)
    results = soup.select('results')
    if len(results) != 1:
        offline = soup.select('offline')
        title = soup.select('title')
        if len(offline) > 0:
            print("エラー：短時間に実行しすぎた可能性があります．", file = stderr)
            for line in offline:
                print(f"{line.text}", file = stderr)
        elif len(title) > 0 and title[0].text == "504 Gateway Timeout":
            print("エラー：実行に時間がかかりすぎているようです．", file = stderr)
        else:
            print(f"other error\nresults: {results}\ntext:{res.text}", file = stderr)
        exit(1)
    outputs = soup.select('results > line')
    for line in outputs:
        print(line.text)
    if errored:
        exit(1)

def main():
    try:
        contents = load(args.filename)
    except Exception as e:
        print(str(e), file = stderr)
        exit(1)
    if not args.leave_comments and not args.no_trim:
        contents = remove_comments(contents)
    if not args.no_trim:
        contents = remove_spaces_around_assignment_operators(contents)
    if args.stdout:
        print(contents)
    elif args.send:
        send_and_print_result(contents)
    else:
        copy_to_clipboard(contents)

main()
