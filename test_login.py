#!/usr/bin/env python3
# 测试 Alist 登录功能

import requests

BASE_URL = "http://localhost:5244"

# 测试登录接口
def test_login(username, password):
    url = f"{BASE_URL}/api/auth/login"
    payload = {"username": username, "password": password}
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        print(f"状态码：{resp.status_code}")
        data = resp.json()
        print(f"响应：{json.dumps(data, indent=2, ensure_ascii=False)}")
        
        if data.get("code") == 200:
            token = data.get("data", {}).get("token", "")
            print(f"\n✅ 登录成功！Token: {token[:20]}...")
            return token
        else:
            print(f"\n❌ 登录失败：{data.get('message', '')}")
            return None
    except Exception as e:
        print(f"❌ 错误：{e}")
        return None

if __name__ == "__main__":
    import json
    print("🐾 测试 Alist 登录")
    print("=" * 50)
    
    # 从命令行获取或输入
    import sys
    if len(sys.argv) >= 3:
        username = sys.argv[1]
        password = sys.argv[2]
    else:
        username = input("用户名：").strip()
        password = input("密码：").strip()
    
    test_login(username, password)
