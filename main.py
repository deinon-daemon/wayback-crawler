## sometimes the most premium proxy is the friends we made along the way...@bcarsley 08/24/23

import re
import bs4
import requests
import cloudscraper
import functions_framework
import urllib.parse as urlparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup



scraper = cloudscraper.CloudScraper()

def get_clean_text(html):

  # Check if we got an error snippet from redirect
  error_div = html.find("div", id="error")
  if error_div and error_div.select('h2')[0].get_text() == "Hrm.":
    # Snippet exists, return empty string
    return " "

  # Remove script tags to remove wayback shtuffs
  #for script in html.find_all('script'):
      #script.decompose()

  ## Comment ^^ in if the scraper starts spitting out 
  ## too much wayback nonsense for the LLMs downstream

  # Find div with id="wm-capinfo"
  div_to_remove = html.find("div", id="wm-capinfo")

  # Remove the div
  if div_to_remove:
    div_to_remove.decompose()    

  text = html.get_text()
  print('text: ', text)
  text = ' '.join([item for item in text.split(' ') if len(item) <= 20])
  text = re.sub(r'\s+', ' ', text) # replace whitespace with double space
  text = re.sub(r'\n', '  ', text)
  return text


def filter_links(links, paths, url, date_of_scrape):
    schema_to_seek = 'https://web.archive.org/web/'+date_of_scrape+'/'

    urls = list(set([schema_to_seek+urljoin(url, path) for path in paths])) + list(set(links))
    print(urls)
    return [
        link for link in urls
        if link.startswith(schema_to_seek+url) and not link.endswith('.pdf') and not link.endswith('.doc') \
        and '#' not in link
    ]

def check_links(links, paths, url, date_of_scrape):

    best_subpaths = [
        "/contact",
        "/about",
        "/resources",
        "/programs"
    ]

    sitemap_subpaths = [
        "/news", "/events", "/jobs", "/apply", "/join", "/team", "/partners",
        "/services", "/products", "/solutions", "/careers", "/blog", "/faq", 
        "/press",
    ]

    best = set()
    ordered = set()

    resolved_links = filter_links(links, paths, url, date_of_scrape)

    for link in resolved_links:
        if any(urlparse.urlparse(link).path.startswith(path) for path in best_subpaths):
            best.add(link)
        elif any(urlparse.urlparse(link).path.startswith(path) or urlparse.urlparse(link).path.endswith(path) for path in sitemap_subpaths):
            ordered.add(link)

    ##print(resolved_links)
    all_links = list(best) + list(ordered)

    return all_links + [link for link in resolved_links if link not in all_links and link != url and link != url + '/']



def call_href_desk(target):

  query_endpoint = 'https://web.archive.org/cdx/search/cdx?url='
  webpage_endpoint = 'https://web.archive.org/web/'
  resp = scraper.get(query_endpoint+target+'&output=json')
  last_record = resp.json()[-1]
  date_of_scrape = last_record[1]
  url = last_record[2]

  response = scraper.get(webpage_endpoint+date_of_scrape+'/'+url)
  return date_of_scrape, response.content


def crawl(url, date_of_scrape):
  html = scraper.get(url).content
  soup = BeautifulSoup(html, 'html.parser')
  text = get_clean_text(soup)
  print("crawled: ", text)
  links = []
  paths = []
  for link in soup.select('a'): 
    href = link.get('href')
    if href:
      if href.startswith('http'):
        links.append(href)  
      else:
        paths.append(href)

  return links, paths, text  
  



def spyder_internet_archive(link):
  date_of_scrape, html = call_href_desk(link)
  soup = BeautifulSoup(html, 'html.parser')
  text = ''
  text += get_clean_text(soup)

  subpaths = []
  first_links = []
  visited_links = []
  paths = []

  for new_link in soup.select('a'): 
      href = new_link.get('href')
      if href:
        if href.startswith('http'):
          first_links.append(href)  
        else:
          paths.append(href)

  ##print(paths)
  ##print(first_links)
  filtered = [item for item in check_links(first_links, paths, link, date_of_scrape) if item != link and item != link+'/']
  if len(filtered) > 0:
    ##print(filtered)
    subpaths.extend(filtered)

    for subpath in filtered:
      try:
        new_links, paths, new_text = crawl(subpath, date_of_scrape)
        ##print(new_text)
        visited_links.append(subpath)
        text += new_text or ' '
        subpaths.extend(check_links(new_links, paths, link, date_of_scrape))
        


      except Exception as e:
        print(f'Crawl failed for: {subpath} ...', e)  
        pass

      if len(visited_links) > 6:
        break

  schema_to_seek = 'https://web.archive.org/web/'+date_of_scrape+'/'

  return {
      "url": link,
      "text": text,
      "subdomains": [item.replace(schema_to_seek,'') for item in subpaths],
      "all_links": [item.replace(schema_to_seek,'') for item in subpaths],
      "visited_links": [item.replace(schema_to_seek,'') for item in visited_links]
  }






@functions_framework.http
def hello_wayback(request):
    """HTTP Cloud Function.
    Args:
        request (flask.Request): The request object.
        <https://flask.palletsprojects.com/en/1.1.x/api/#incoming-request-data>
    Returns:
        The response text, or any set of values that can be turned into a
        Response object using `make_response`
        <https://flask.palletsprojects.com/en/1.1.x/api/#flask.make_response>.
    """
    request_json = request.get_json(silent=True)
    request_args = request.args

    if request_json and 'url' in request_json:
        url = request_json['url']
        return spyder_internet_archive(url)
    else:
        name = 'World'
    return 'Hello {}!'.format(name)
