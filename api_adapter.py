# -*- coding: utf-8 -*-
import requests
import json
import traceback
from api_config import API_CONFIGS
import os

class APIAdapter:
    def __init__(self, api_name=None, appcode=None):
        self.api_name = api_name or API_CONFIGS['default']
        self.config = API_CONFIGS['apis'].get(self.api_name)
        if not self.config:
            raise ValueError(f"API configuration '{self.api_name}' not found")
        
        # 优先级：传入的appcode > 配置文件中的appcode > 环境变量中的appcode
        self.appcode = appcode or self.config.get('appcode') or os.getenv('APPCODE', '')
    
    def _parse_path(self, path, data):
        """解析路径表达式，如 'data.details[0]'"""
        result = data
        parts = path.split('.')
        for part in parts:
            if '[' in part and ']' in part:
                key, index = part.split('[')
                index = int(index[:-1])
                result = result[key][index]
            else:
                result = result.get(part, {})
        return result
    
    def call_api(self, isbn):
        try:
            # 构建请求URL
            url = self.config['url']
            
            # 构建请求头
            headers = {}
            for key, value in self.config['headers'].items():
                headers[key] = value.format(appcode=self.appcode)
            
            # 构建请求参数
            params = {}
            for key, value in self.config['params'].items():
                params[key] = value.format(isbn=isbn)
            
            print(f"[INFO] Calling {self.config['name']} for ISBN: {isbn}")
            print(f"[INFO] API URL: {url}")
            print(f"[INFO] Method: {self.config['method']}")
            
            # 发送请求
            if self.config['method'].upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif self.config['method'].upper() == 'POST':
                response = requests.post(url, headers=headers, data=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {self.config['method']}")
            
            response.raise_for_status()
            data = response.json()
            
            status_field = self.config['response_mapping']['status']
            msg_field = self.config['response_mapping']['msg']
            print(f"[INFO] API Response received: {status_field}={data.get(status_field)}, {msg_field}={data.get(msg_field)}")
            
            # 检查请求是否成功
            status_field = self.config['response_mapping']['status']
            success_status = self.config['response_mapping']['success_status']
            
            # 特殊处理OpenLibrary的存在检查
            if self.api_name == 'openlibrary':
                data_path = self.config['response_mapping']['data'].format(isbn=isbn)
                if data_path not in data:
                    print(f'[ERROR] API Error: Book not found in OpenLibrary')
                    return None
            else:
                if data.get(status_field) != success_status:
                    print(f'[ERROR] API Error: {data.get(self.config["response_mapping"]["msg"], "Unknown error")}')
                    return None
            
            # 解析数据
            data_path = self.config['response_mapping']['data']
            if self.api_name == 'openlibrary':
                data_path = data_path.format(isbn=isbn)
            result_data = self._parse_path(data_path, data)
            
            print(f"[INFO] Parsed data path: {data_path}")
            print(f"[INFO] Result data keys: {list(result_data.keys())}")
            
            # 映射字段
            fields = self.config['response_mapping']['fields']
            
            # 处理OpenLibrary特殊字段
            def format_authors(authors):
                if isinstance(authors, list):
                    return ', '.join([author.get('name', '') for author in authors])
                return str(authors)
            
            def format_publishers(publishers):
                if isinstance(publishers, list):
                    return ', '.join([publisher.get('name', '') for publisher in publishers])
                return str(publishers)
            
            def format_language(languages):
                if isinstance(languages, list):
                    return languages[0].get('key', '').split('/')[-1] if languages else ''
                return str(languages)
            
            def format_cover(cover):
                if isinstance(cover, dict):
                    return cover.get('medium', '')
                return str(cover)
            
            def format_description(description):
                if isinstance(description, dict):
                    return description.get('value', '')
                return str(description)
            
            mapped_data = {
                'isbn': isbn,
                'title': result_data.get(fields['title'], ''),
                'authors': format_authors(result_data.get(fields['author'], '')),
                'publisher': format_publishers(result_data.get(fields['publisher'], '')),
                'publish_date': result_data.get(fields['pubdate'], ''),
                'pages': int(result_data.get(fields['page'], 0)) if result_data.get(fields['page']) else None,
                'language': format_language(result_data.get(fields['language'], '')),
                'cover_url': format_cover(result_data.get(fields['pic'], '')),
                'description': format_description(result_data.get(fields['summary'], ''))
            }
            
            print(f"[INFO] Successfully fetched book: {mapped_data['title']} by {mapped_data['authors']}")
            
            return mapped_data
            
        except Exception as e:
            print(f'[ERROR] Error fetching book {isbn} from {self.config["name"]}: {e}')
            traceback.print_exc()
            return None