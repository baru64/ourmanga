import logging
import argparse
import re
from datetime import datetime
from typing import Any, Tuple, List
from pathlib import Path
from fpdf import FPDF

from bs4 import BeautifulSoup
from PIL import Image
import requests

logger = logging.getLogger(__name__)

jpg_pattern = re.compile(".*/[0-9]*\.jpg")
png_pattern = re.compile(".*/[0-9]*\.png")


def convert_grayscale(imgpath: str):
    im = Image.open(imgpath)
    im = im.convert('L')
    im.save(imgpath)


def download_image(
    session: requests.Session,
    url: str,
    path: Path,
    index: int,
    format_str: str
):
    file = path / f'{index}{format_str}'
    logger.debug(f'downloading {url} to {file}')
    with file.open('wb') as f:
        response = session.get(url)
        if response.status_code == 200:
            f.write(response.content)
        else:
            print(f'Error: cannot download {url}')


def scrape_image_urls(
    session: requests.Session, url: str
) -> Tuple[List[str], str]:
    """ Download page and parse image urls  """
    def filter_jpg(img: str):
        return jpg_pattern.match(img['src'].strip()) is not None

    def filter_png(img: str):
        return png_pattern.match(img['src'].strip()) is not None
    response = None
    try:
        response = session.get(url)
    except Exception as e:
        print(f'Error: cannot download {args.url}')
        logger.debug(str(e))
        return
    soup = BeautifulSoup(response.content, 'html.parser')
    print(f'> title: {soup.title.string}')
    all_images = soup.find_all('img')
    image_urls = [img['src'] for img in filter(filter_jpg, all_images)]
    format_str = '.jpg'
    if len(image_urls) < 1:
        image_urls = [img['src'] for img in filter(filter_png, all_images)]
        # for some reason it's jpeg with .png extension
        # format_str = '.png'
    return image_urls, format_str


def make_pdf(image_files: str, pdf_file: str):
    """ Outputs pdf with images to given file  """
    print(f'> creating pdf {pdf_file}...')
    # find the biggest page size
    page_size = (0, 0)
    for image in image_files:
        im = Image.open(image)
        if im.size[1] > im.size[0] and sum(im.size) > sum(page_size):
            page_size = im.size
    pdf = FPDF(unit="pt", format=page_size)
    for image in image_files:
        im = Image.open(image)
        pdf.add_page()
        pdf.image(str(image), 0, 0, im.size[0], im.size[1])
    pdf.output(pdf_file, "F")


def download_chapter(
    session: requests.Session,
    url: str,
    output_dir: str,
    filename: str,
    keep: bool
):
    """ Download chapter to pdf file  """
    print(f'> downloading chapter {args.url}...')
    image_urls, format_str = scrape_image_urls(session, url)
    if len(image_urls) < 1:
        logger.error("Something went wrong, can't get image urls")
        return
    logger.debug(image_urls)
    dir_path = Path(output_dir)
    if not dir_path.exists():
        dir_path.mkdir(parents=True)
    elif not dir_path.is_dir():
        logger.error(f'Error: {dir_path} is not a directory')
        return
    # download images
    for idx, url in enumerate(image_urls):
        download_image(session, url, dir_path, idx, format_str)
    # convert images to grayscale
    for image_file in dir_path.iterdir():
        convert_grayscale(image_file)
    # create pdf with images
    image_files = [file for file in dir_path.iterdir()]
    image_files.sort(key=lambda img: int(img.name[:-4]))
    make_pdf(
        [str(image_file) for image_file in image_files],
        str(dir_path / '..' / filename) + '.pdf'
    )
    # remove image files
    if not keep:
        print('> removing image files')
        for file in dir_path.iterdir():
            if str(file).find('.jpg') != -1:
                file.unlink()
        dir_path.rmdir()


# TODO: check if kissmanga or different page
def main(args: Any):
    logger.debug("starting main")
    print((34 * '=') + ' OURmanga ' + (35 * '='))
    session = requests.Session()
    if args.chapters is None:
        download_chapter(
            session, args.url, args.output, args.filename, args.keep
        )
    else:
        if args.chapters.find(',') != -1:
            chapters = args.chapters.split(',')
        elif args.chapters.find('-') != -1:
            chapters_num = [int(ch) for ch in args.chapters.split('-')]
            chapters = range(chapters_num[0], chapters_num[1] + 1)
        for chapter in chapters:
            chapter_url = args.url + f'/chapter-{chapter}'
            output = args.output + f'_ch_{chapter}'
            filename = args.filename + f'_chapter_{chapter}'
            download_chapter(session, chapter_url, output, filename, args.keep)
    print('> done.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download OUR manga")
    parser.add_argument('url', type=str, help='url to manga chapter')
    parser.add_argument('-d', '--debug', action="store_true",
                        help="print debug log")
    parser.add_argument('-k', '--keep', action="store_true",
                        help="keep images")
    date_now = datetime.now().strftime('%Y-%m-%d-%H%M%S')
    parser.add_argument('-o', '--output', type=str,
                        default=f'./downloads/{date_now}',
                        help='output directory')
    parser.add_argument(
        '-c', '--chapters', type=str, default=None,
        help='specify chapters to download, format: 9-23 or 1,2,3')
    parser.add_argument('-n', '--filename', type=str, default='out',
                        help='output file name')
    args = parser.parse_args()
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    main(args)
