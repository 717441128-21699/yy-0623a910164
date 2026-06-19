import base64
import json
import requests
from datetime import date, timedelta

BASE_URL = "http://localhost:8000"
API_KEY = ""


def create_test_image(width=640, height=480, color=(200, 200, 200)):
    from PIL import Image
    import io
    img = Image.new('RGB', (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def headers():
    h = {"Content-Type": "application/json"}
    if API_KEY:
        h["X-API-Key"] = API_KEY
    return h


def test_01_root():
    print("=" * 60)
    print("测试1: 获取系统信息")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/")
    data = response.json()
    print(f"服务名称: {data.get('name')} v{data.get('version')}")
    print(f"需要API Key: {data.get('require_api_key')}")
    assert data.get("status") == "running"
    print("✓ 通过\n")


def test_02_create_client():
    global API_KEY
    print("=" * 60)
    print("测试2: 创建接入方")
    print("=" * 60)
    payload = {
        "name": "测试诊所A",
        "client_type": "clinic",
        "contact_name": "王医生",
        "contact_phone": "13800138000",
        "contact_email": "wang@clinic-a.com"
    }
    response = requests.post(f"{BASE_URL}/api/clients", json=payload)
    data = response.json()
    print(f"接入方名称: {data.get('name')}")
    print(f"API Key: {data.get('api_key')}")
    print(f"接入方类型: {data.get('client_type')}")
    assert data.get("api_key", "").startswith("ak_")
    API_KEY = data.get("api_key")
    print("✓ 通过\n")


def test_03_list_clients():
    print("=" * 60)
    print("测试3: 获取接入方列表")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/api/clients")
    data = response.json()
    print(f"接入方总数: {data.get('total')}")
    for c in data.get("clients", []):
        print(f"  - {c['name']} (API调用: {c['total_api_calls']}, 异常照片: {c['total_abnormal_photos']})")
    assert data.get("total") >= 2
    print("✓ 通过\n")


def test_04_submit_photos_with_url():
    print("=" * 60)
    print("测试4: 提交初诊照片(验证公开URL)")
    print("=" * 60)
    test_img = create_test_image()
    angles = ["正面面相", "侧面面相", "口内正面像", "口内左侧面像"]
    photos = [{"angle": a, "image_base64": test_img} for a in angles]
    payload = {
        "patient_no": "P-EMBED-001",
        "patient_name": "李四",
        "visit_date": "2024-06-01",
        "is_initial": True,
        "photos": photos
    }
    response = requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers())
    data = response.json()
    print(f"提交状态: {'成功' if data.get('success') else '失败'}")
    print(f"已提交: {data['completeness']['submitted_count']}/{data['completeness']['total_required']}")
    for p in data.get("photos", []):
        print(f"  - {p['angle']}: URL={p['file_url']}, 质量合格={p['quality_passed']}")
        if p.get("file_url"):
            assert p["file_url"].startswith("/static/photos/"), f"URL格式错误: {p['file_url']}"
            print(f"    ✓ URL格式正确，不含磁盘路径")
    print("✓ 通过\n")


def test_05_submit_second_visit():
    print("=" * 60)
    print("测试5: 提交复诊照片(带API Key)")
    print("=" * 60)
    test_img = create_test_image(color=(180, 200, 180))
    angles = ["正面面相", "侧面面相", "45°侧面面相", "口内正面像", "口内左侧面像", "口内右侧面像"]
    photos = [{"angle": a, "image_base64": test_img} for a in angles]
    payload = {
        "patient_no": "P-EMBED-001",
        "visit_date": "2024-06-20",
        "is_initial": False,
        "photos": photos
    }
    response = requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers())
    data = response.json()
    print(f"提交状态: {'成功' if data.get('success') else '失败'}")
    print(f"缺失角度: {', '.join(data['completeness']['missing_angles'])}")
    print(f"质量待改善: {data['completeness']['quality_failed_count']} 张")
    print("✓ 通过\n")


def test_06_compare_with_public_url():
    print("=" * 60)
    print("测试6: 生成对比图(验证公开URL)")
    print("=" * 60)
    payload = {
        "patient_no": "P-EMBED-001",
        "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-20"
    }
    response = requests.post(f"{BASE_URL}/api/compare/generate", json=payload, headers=headers())
    data = response.json()
    print(f"状态: {'成功' if data.get('success') else '失败'}")
    print(f"对比图URL: {data.get('compare_image_url')}")
    print(f"AI提示: {data.get('ai_hint', '')[:80]}...")
    assert data["compare_image_url"].startswith("/static/compare/"), f"URL格式错误: {data['compare_image_url']}"
    print("✓ 对比图URL格式正确，不含磁盘路径")

    if data.get("compare_image_url"):
        img_resp = requests.get(f"{BASE_URL}{data['compare_image_url']}")
        print(f"对比图可访问: HTTP {img_resp.status_code}, 大小: {len(img_resp.content)} bytes")
        assert img_resp.status_code == 200
        print("✓ 对比图可直接通过URL访问")
    print("✓ 通过\n")


def test_07_logs_with_filters():
    print("=" * 60)
    print("测试7: 调用日志多维度筛选")
    print("=" * 60)

    print("7.1 按接口分类筛选(compare):")
    resp = requests.get(f"{BASE_URL}/api/admin/logs?api_category=compare&limit=5")
    data = resp.json()
    print(f"  对比类接口调用数: {data.get('total')}")
    for log in data.get("logs", []):
        print(f"    {log['method']} {log['endpoint']} - {log['status_code']} - {log.get('client_name', '未认证')}")

    print("7.2 按状态码类别筛选(2xx成功):")
    resp = requests.get(f"{BASE_URL}/api/admin/logs?status_code=2&limit=3")
    data = resp.json()
    print(f"  成功调用数: {data.get('total')}")

    print("7.3 按日期范围筛选:")
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    resp = requests.get(f"{BASE_URL}/api/admin/logs?date_from={yesterday}&date_to={tomorrow}&limit=3")
    data = resp.json()
    print(f"  今日+前后: {data.get('total')} 条记录")

    print("7.4 按患者编号筛选:")
    resp = requests.get(f"{BASE_URL}/api/admin/logs?patient_no=P-EMBED-001&limit=3")
    data = resp.json()
    print(f"  患者P-EMBED-001: {data.get('total')} 条记录")

    print("7.5 按接入方ID筛选:")
    clients_resp = requests.get(f"{BASE_URL}/api/clients?limit=1")
    client_id = clients_resp.json()["clients"][0]["id"]
    resp = requests.get(f"{BASE_URL}/api/admin/logs?client_id={client_id}&limit=3")
    data = resp.json()
    print(f"  接入方{client_id}: {data.get('total')} 条记录")

    print("✓ 通过\n")


def test_08_create_callback_config():
    print("=" * 60)
    print("测试8: 创建回调配置")
    print("=" * 60)
    clients_resp = requests.get(f"{BASE_URL}/api/clients?limit=1")
    client = clients_resp.json()["clients"][0]

    payload = {
        "client_id": client["id"],
        "event_type": "photo_submitted",
        "callback_url": "http://localhost:9999/webhook/photos",
        "secret_token": "my-secret-token",
        "max_retries": 3,
        "retry_interval": 30
    }
    response = requests.post(f"{BASE_URL}/api/callbacks/configs", json=payload)
    data = response.json()
    print(f"回调配置ID: {data.get('id')}")
    print(f"事件类型: {data.get('event_type')}")
    print(f"回调地址: {data.get('callback_url')}")
    print(f"最大重试: {data.get('max_retries')} 次")
    assert data.get("event_type") == "photo_submitted"
    print("✓ 通过\n")


def test_09_submit_triggers_callback():
    print("=" * 60)
    print("测试9: 提交照片触发回调任务")
    print("=" * 60)
    test_img = create_test_image()
    photos = [{"angle": "正面面相", "image_base64": test_img}]
    payload = {
        "patient_no": "P-CALLBACK-001",
        "visit_date": "2024-06-20",
        "photos": photos
    }
    response = requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers())
    assert response.json().get("success") == True

    tasks_resp = requests.get(f"{BASE_URL}/api/callbacks/tasks?event_type=photo_submitted&limit=5")
    tasks_data = tasks_resp.json()
    print(f"回调任务总数: {tasks_data.get('total')}")
    for t in tasks_data.get("tasks", []):
        print(f"  - [{t['status']}] {t['patient_no']} 重试: {t['retry_count']}/{t['max_retries']} 错误: {t['last_error'][:30]}")
    assert tasks_data.get("total") >= 1
    print("✓ 回调任务已创建\n")


def test_10_client_stats():
    print("=" * 60)
    print("测试10: 按接入方维度统计")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/api/admin/client-stats")
    data = response.json()
    print(f"接入方数量: {data.get('total')}")
    for s in data.get("stats", []):
        print(f"  {s['client_name']} ({s['client_type']}):")
        print(f"    API调用: 总计{s['total_api_calls']} 成功{s['success_calls']} 失败{s['failed_calls']}")
        print(f"    照片: {s['total_photos']}张 (异常{s['abnormal_photos']}张) 对比: {s['total_compares']}次")
    assert data.get("total") >= 2
    print("✓ 通过\n")


def test_11_logs_all_interfaces():
    print("=" * 60)
    print("测试11: 验证所有接口都留下记录")
    print("=" * 60)
    response = requests.get(f"{BASE_URL}/api/admin/logs?limit=100")
    data = response.json()
    endpoints = set(log["endpoint"] for log in data.get("logs", []))
    categories = set(log.get("api_category", "") for log in data.get("logs", []))
    print(f"记录的接口数: {len(endpoints)}")
    print(f"接口分类: {', '.join(categories)}")
    assert any("/api/photos" in e for e in endpoints), "照片接口未记录"
    assert any("/api/compare" in e for e in endpoints), "对比接口未记录"
    assert any("/api/clients" in e for e in endpoints), "接入方接口未记录"
    assert any("/api/admin" in e for e in endpoints), "管理员接口未记录"
    print("✓ 所有类型接口均已记录日志\n")


def main():
    print("\n" + "╔" + "=" * 58 + "╗")
    print("║    正畸复诊拍照对比服务 - 嵌入能力增强版测试套件    ║")
    print("╚" + "=" * 58 + "╝\n")

    tests = [
        test_01_root,
        test_02_create_client,
        test_03_list_clients,
        test_04_submit_photos_with_url,
        test_05_submit_second_visit,
        test_06_compare_with_public_url,
        test_07_logs_with_filters,
        test_08_create_callback_config,
        test_09_submit_triggers_callback,
        test_10_client_stats,
        test_11_logs_all_interfaces,
    ]

    results = []
    for test in tests:
        try:
            test()
            results.append(True)
        except Exception as e:
            print(f"✗ 测试失败: {e}\n")
            import traceback
            traceback.print_exc()
            results.append(False)

    passed = sum(results)
    total = len(results)
    print("=" * 60)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 60)
    if passed == total:
        print("🎉 所有测试通过！嵌入能力增强版运行正常。")
    else:
        print(f"⚠️  有 {total - passed} 个测试失败。")


if __name__ == "__main__":
    main()
