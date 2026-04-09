# -*- coding: utf-8 -*-
import os
import requests
import base64
from io import BytesIO
from dotenv import load_dotenv
import tos

load_dotenv()

class TOSClient:
    """火山引擎 TOS 对象存储客户端"""

    def __init__(self):
        self.access_key_id = os.getenv('TOS_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('TOS_SECRET_ACCESS_KEY')
        self.endpoint = os.getenv('TOS_ENDPOINT', 'tos-cn-beijing.volces.com')
        self.bucket_name = os.getenv('TOS_BUCKET_NAME', 'bookcase-img')
        self.region = os.getenv('TOS_REGION', 'cn-beijing')

        # 初始化 TOS 认证和客户端
        auth = tos.Auth(self.access_key_id, self.secret_access_key, self.region)
        self.client = tos.TosClient(
            auth=auth,
            endpoint=self.endpoint
        )

    def upload_image_from_url(self, image_url: str, object_key: str = None) -> str:
        """
        从 URL 下载图片并上传到 TOS

        Args:
            image_url: 图片的原始 URL
            object_key: 存储在 TOS 中的对象键（路径），如果为 None 则自动生成

        Returns:
            TOS 上的图片访问 URL
        """
        if not image_url:
            return None

        try:
            # 下载图片
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(image_url, headers=headers, timeout=30)
            response.raise_for_status()

            # 获取图片内容
            image_data = response.content

            # 如果没有指定 object_key，从 URL 中提取文件名
            if not object_key:
                # 从 URL 中提取文件名
                from urllib.parse import urlparse
                parsed_url = urlparse(image_url)
                filename = os.path.basename(parsed_url.path)
                if not filename:
                    filename = 'cover.jpg'
                # 添加时间戳避免冲突
                import time
                timestamp = int(time.time())
                object_key = f"covers/{timestamp}_{filename}"

            # 确定 Content-Type
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            if not content_type.startswith('image/'):
                content_type = 'image/jpeg'

            # 上传到 TOS - 使用大写参数名
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=BytesIO(image_data),
                ContentType=content_type
            )

            # 构建访问 URL
            # 格式: https://{bucket}.{endpoint}/{object_key}
            tos_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"

            print(f"[INFO] Image uploaded to TOS: {tos_url}")
            return tos_url

        except requests.RequestException as e:
            print(f"[ERROR] Failed to download image from URL: {e}")
            return None
        except Exception as e:
            print(f"[ERROR] Failed to upload image to TOS: {e}")
            return None

    def upload_image_from_bytes(self, image_data: bytes, object_key: str, content_type: str = 'image/jpeg') -> str:
        """
        上传图片字节数据到 TOS

        Args:
            image_data: 图片的二进制数据
            object_key: 存储在 TOS 中的对象键（路径）
            content_type: 图片的 MIME 类型

        Returns:
            TOS 上的图片访问 URL
        """
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=BytesIO(image_data),
                ContentType=content_type
            )

            # 构建访问 URL
            tos_url = f"https://{self.bucket_name}.{self.endpoint}/{object_key}"

            print(f"[INFO] Image uploaded to TOS: {tos_url}")
            return tos_url

        except Exception as e:
            print(f"[ERROR] Failed to upload image to TOS: {e}")
            return None

    def delete_object(self, object_key: str) -> bool:
        """
        删除 TOS 上的对象

        Args:
            object_key: 要删除的对象键

        Returns:
            是否删除成功
        """
        try:
            self.client.delete_object(
                Bucket=self.bucket_name,
                Key=object_key
            )
            print(f"[INFO] Object deleted from TOS: {object_key}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to delete object from TOS: {e}")
            return False

    def extract_object_key_from_url(self, url: str) -> str:
        """
        从 TOS URL 中提取 object_key

        Args:
            url: TOS 访问 URL

        Returns:
            object_key
        """
        # URL 格式: https://{bucket}.{endpoint}/{object_key}
        prefix = f"https://{self.bucket_name}.{self.endpoint}/"
        if url.startswith(prefix):
            return url[len(prefix):]
        return None


# 单例实例
tos_client = TOSClient()
