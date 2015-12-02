# -*- coding: utf-8 -*-

from woocommerce import API

api = API(url='http://localhost/wordpress/',
          consumer_key='ck_82252170aadf3dcf1a60272a8e9c52793a991067',
          consumer_secret='cs_fa64fe546a91d32e94b7bd2c6a8a7ceee84053c2',
          version='v2')

if api:
    print(api.post('products', {}).status_code)