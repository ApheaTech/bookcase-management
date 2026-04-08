# API配置文件
# 支持多个API接口的配置和参数映射

API_CONFIGS = {
    'default': 'jisuisbn',
    'apis': {
        'jisuisbn': {
            'name': '极速数据ISBN查询API',
            'url': 'https://jisuisbn.market.alicloudapi.com/isbn/query',
            'appcode': '5b707e44b76849c99dceabb36ff05ba1',
            'method': 'GET',
            'headers': {
                'Authorization': 'APPCODE {appcode}',
                'Content-Type': 'application/json; charset=UTF-8'
            },
            'params': {
                'isbn': '{isbn}'
            },
            'response_mapping': {
                'status': 'status',
                'msg': 'msg',
                'success_status': 0,
                'data': 'result',
                'fields': {
                    'title': 'title',
                    'author': 'author',
                    'publisher': 'publisher',
                    'pubdate': 'pubdate',
                    'page': 'page',
                    'language': 'language',
                    'pic': 'pic',
                    'summary': 'summary'
                }
            }
        },
        'jumeiisbn': {
            'name': '聚美智数ISBN查询API',
            'url': 'https://jmisbn.market.alicloudapi.com/isbn/query',
            'appcode': '5b707e44b76849c99dceabb36ff05ba1',
            'method': 'POST',
            'headers': {
                'Authorization': 'APPCODE {appcode}',
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
            },
            'params': {
                'isbn': '{isbn}'
            },
            'response_mapping': {
                'status': 'code',
                'msg': 'msg',
                'success_status': 200,
                'data': 'data.details[0]',
                'fields': {
                    'title': 'title',
                    'author': 'author',
                    'publisher': 'publisher',
                    'pubdate': 'pubDate',
                    'page': 'page',
                    'language': 'language',
                    'pic': 'img',
                    'summary': 'gist'
                }
            }
        },
        'openlibrary': {
            'name': 'OpenLibrary ISBN查询API',
            'url': 'https://openlibrary.org/api/books',
            'appcode': '',
            'method': 'GET',
            'headers': {
                'Content-Type': 'application/json; charset=UTF-8'
            },
            'params': {
                'bibkeys': 'ISBN:{isbn}',
                'format': 'json',
                'jscmd': 'data'
            },
            'response_mapping': {
                'status': 'exists',
                'msg': 'msg',
                'success_status': True,
                'data': 'ISBN:{isbn}',
                'fields': {
                    'title': 'title',
                    'author': 'authors',
                    'publisher': 'publishers',
                    'pubdate': 'publish_date',
                    'page': 'number_of_pages',
                    'language': 'languages',
                    'pic': 'cover',
                    'summary': 'description'
                }
            }
        }
    }
}