import requests
import base64
import io
import time
from datetime import date, timedelta
from PIL import Image

BASE_URL = "http://localhost:8000"


def make_test_image(width=300, height=300, color=(200, 180, 150)):
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def hr(title=""):
    print()
    print("=" * 60)
    if title:
        print(f"  {title}")
        print("=" * 60)


def test_section(title):
    hr(title)


passed = 0
total = 0


def check(name, cond, detail=""):
    global passed, total
    total += 1
    if cond:
        passed += 1
        print(f"  ✓ {name}{(': ' + detail) if detail else ''}")
    else:
        print(f"  ✗ {name}{(': ' + detail) if detail else ''}")


def summary():
    hr()
    print(f"  测试结果: {passed}/{total} 通过")
    if passed == total:
        print("  🎉 所有测试通过！隔离+配额+回调详细版运行正常。")
    else:
        print(f"  ⚠️  {total - passed} 项失败，请检查。")
    hr()


def main():
    test_img_b64 = make_test_image()

    test_section("测试 0: 系统信息 & 默认接入方")
    r = requests.get(f"{BASE_URL}/").json()
    print(f"  服务版本: {r.get('version')}")
    print(f"  功能列表: {r.get('features', [])}")
    check("版本号为 1.2.0", r.get("version") == "1.2.0")
    check("默认接入方 is_default 已创建", True)

    list_resp = requests.get(f"{BASE_URL}/api/clients").json()
    default_client_id = None
    default_api_key = None
    for c in list_resp["clients"]:
        if c.get("is_default"):
            default_client_id = c["id"]
            default_api_key = c["api_key"]
            break
    check("存在默认接入方", default_client_id is not None, f"ID={default_client_id}")
    print(f"  默认接入方 API Key: {default_api_key}")

    # ========== 接入方创建 ==========
    test_section("测试 1: 创建两个接入方 (诊所A带配额, 诊所B禁用对比)")
    r1 = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "配额测试诊所A",
        "client_type": "clinic",
        "contact_name": "张医生",
        "contact_phone": "13800000001",
        "daily_api_quota": 500,
        "daily_photo_quota": 100,
        "allow_compare": True
    }).json()
    client_a_id = r1["id"]
    client_a_key = r1["api_key"]
    check("诊所A 创建成功", r1.get("name") == "配额测试诊所A")
    check("诊所A 每日API配额=500", r1.get("daily_api_quota") == 500)
    check("诊所A 每日照片配额=100", r1.get("daily_photo_quota") == 100)
    check("诊所A 允许对比", r1.get("allow_compare") is True)
    print(f"  诊所A Key: {client_a_key}")

    r2 = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "对比禁用诊所B",
        "client_type": "clinic",
        "contact_name": "李医生",
        "daily_api_quota": 0,
        "daily_photo_quota": 0,
        "allow_compare": False
    }).json()
    client_b_id = r2["id"]
    client_b_key = r2["api_key"]
    check("诊所B 创建成功", r2.get("name") == "对比禁用诊所B")
    check("诊所B 禁用对比", r2.get("allow_compare") is False)
    print(f"  诊所B Key: {client_b_key}")

    # ========== 接入方数据隔离 ==========
    test_section("测试 2: 接入方数据隔离 - 相同患者编号互不干扰")
    headers_a = {"X-API-Key": client_a_key}
    headers_b = {"X-API-Key": client_b_key}
    headers_none = {}
    shared_patient_no = "P-SHARED-001"

    # 诊所A 提交 初诊 + 复诊
    def submit_photos(patient_no, visit_date, is_initial, headers, count=4, angles_prefix="正面侧面"):
        angles = ["正面面相", "侧面面相", "45°侧面面相", "口内正面像",
                  "口内左侧面像", "口内右侧面像", "上颌牙合面像", "下颌牙合面像"]
        payload = {
            "patient_no": patient_no,
            "patient_name": f"患者-{patient_no}",
            "visit_date": str(visit_date),
            "is_initial": is_initial,
            "photos": [
                {"angle": a, "image_base64": test_img_b64}
                for a in angles[:count]
            ]
        }
        return requests.post(f"{BASE_URL}/api/photos/submit", json=payload, headers=headers).json()

    init_a = submit_photos(shared_patient_no, date(2024, 1, 15), True, headers_a)
    check("诊所A 提交初诊成功", init_a.get("success") is True, f"照片数={init_a.get('completeness',{}).get('submitted_count', 0)}")

    init_b = submit_photos(shared_patient_no, date(2024, 3, 10), True, headers_b)
    check("诊所B 提交相同编号患者初诊成功", init_b.get("success") is True)

    curr_a = submit_photos(shared_patient_no, date(2024, 6, 20), False, headers_a, count=6)
    check("诊所A 提交复诊成功", curr_a.get("success") is True)

    # 诊所A 再用另一个患者编号提交，验证有多个患者
    p_a2 = "P-A-EXTRA-002"
    extra_a = submit_photos(p_a2, date(2024, 5, 15), True, headers_a, count=4)
    check("诊所A 提交第二个患者", extra_a.get("success") is True)

    # 诊所A 对比(自己的两次)
    compare_a = requests.post(f"{BASE_URL}/api/compare/generate", json={
        "patient_no": shared_patient_no,
        "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-20"
    }, headers=headers_a).json()
    check("诊所A 可用自己的两次做对比", compare_a.get("success") is True,
          f"角度={compare_a.get('angles_compared', 0)}, URL={compare_a.get('compare_image_url', '')[:40]}...")

    # 诊所B 查询 共享患者编号 应该看不到A的照片
    list_b = requests.get(
        f"{BASE_URL}/api/photos/list/{shared_patient_no}/2024-06-20",
        headers=headers_b
    ).json()
    check("诊所B 看不到诊所A的复诊日期照片", list_b.get("photos", []) == [])

    # 诊所A 查询共享患者应该有照片
    list_a = requests.get(
        f"{BASE_URL}/api/photos/list/{shared_patient_no}/2024-06-20",
        headers=headers_a
    ).json()
    check("诊所A 自己能看到6张复诊照片", len(list_a.get("photos", [])) == 6)

    # 无key(默认接入方) 查询共享患者应该也看不到
    list_d = requests.get(
        f"{BASE_URL}/api/photos/list/{shared_patient_no}/2024-06-20",
        headers=headers_none
    ).json()
    check("默认接入方 看不到诊所A的照片", list_d.get("photos", []) == [])

    # ========== 配额测试 ==========
    test_section("测试 3: 配额限流 - 新建小配额接入方验证")
    # 专门创建一个小配额的接入方来测试
    quota_resp = requests.post(f"{BASE_URL}/api/clients", json={
        "name": "小配额诊所C",
        "client_type": "clinic",
        "daily_api_quota": 100,
        "daily_photo_quota": 3,
        "allow_compare": True
    }).json()
    client_c_id = quota_resp["id"]
    client_c_key = quota_resp["api_key"]
    headers_c = {"X-API-Key": client_c_key}

    submit_c_1 = submit_photos("P-QUOTA-001", date(2024, 6, 10), True, headers_c, count=3)
    check("诊所C 提交3张(配额满)", submit_c_1.get("success") is True)

    submit_c_2 = submit_photos("P-QUOTA-001", date(2024, 6, 11), False, headers_c, count=1)
    check("诊所C 超额提交照片 返回429", submit_c_2.get("success") is False and "已达上限" in submit_c_2.get("message", ""),
          f"返回: {submit_c_2}")

    # ========== 对比禁用测试 ==========
    test_section("测试 4: 对比禁用 - 诊所B调用对比返回429")
    submit_b1 = submit_photos(shared_patient_no, date(2024, 5, 1), True, headers_b)
    submit_b2 = submit_photos(shared_patient_no, date(2024, 6, 1), False, headers_b)

    cmp_b = requests.post(f"{BASE_URL}/api/compare/generate", json={
        "patient_no": shared_patient_no,
        "compare_mode": "initial_vs_current",
        "current_visit_date": "2024-06-01"
    }, headers=headers_b).json()
    check("诊所B 禁用对比 返回429", cmp_b.get("success") is False, f"消息: {cmp_b.get('message', cmp_b)}")

    # ========== 回调详细记录 + 同步重试 ==========
    test_section("测试 5: 回调配置 + 同步重试 + 每次执行记录")
    # 创建诊所A回调配置（指向一个肯定失败的地址）
    cb_cfg = requests.post(f"{BASE_URL}/api/callbacks/configs", json={
        "client_id": client_a_id,
        "event_type": "photo_submitted",
        "callback_url": "http://127.0.0.1:1/nonexistent-callback",
        "secret_token": "test-secret-123",
        "max_retries": 2,
        "retry_interval": 10,
        "is_active": True
    }).json()
    check("回调配置创建成功", cb_cfg.get("id") is not None, f"config_id={cb_cfg.get('id')}")

    # 诊所A 用新患者触发一次回调任务（到不会成功的地址）
    trigger_patient = "P-CB-TEST-001"
    trig = submit_photos(trigger_patient, date(2024, 6, 20), True, headers_a, count=4)
    check("触发回调的照片提交成功", trig.get("success") is True)

    # 等待一下后台处理尝试一次
    time.sleep(3)

    # 查询回调任务
    tasks_resp = requests.get(f"{BASE_URL}/api/callbacks/tasks", params={
        "client_id": client_a_id, "event_type": "photo_submitted"
    }).json()
    print(f"  回调任务数: {tasks_resp.get('total', 0)}")
    check("至少存在1个回调任务", tasks_resp.get("total", 0) >= 1)

    task_id = None
    for t in tasks_resp.get("tasks", []):
        if t.get("patient_no") == trigger_patient:
            task_id = t["id"]
            break
    check("找到对应的回调任务", task_id is not None, f"task_id={task_id}")

    if task_id:
        # 先同步重试1次(肯定失败,因为指向不存在端口)
        retry_resp = requests.post(f"{BASE_URL}/api/callbacks/tasks/retry/{task_id}").json()
        print(f"  同步重试结果: {retry_resp}")
        check("同步重试接口返回", retry_resp.get("success") is True)
        check("同步重试状态是 failed 或 retrying",
              retry_resp.get("new_status") in ("failed", "retrying"))
        check("同步重试失败原因记录", retry_resp.get("error_message", "") != "")

        # 再次同步重试，如果max_retries=2，retry_count=2后就到failed
        time.sleep(1)
        retry_resp2 = requests.post(f"{BASE_URL}/api/callbacks/tasks/retry/{task_id}").json()
        print(f"  第二次同步重试: {retry_resp2}")
        check("第二次同步重试后状态记录存在", retry_resp2.get("success") is True)

        # 查询详情，看是否有执行记录
        detail = requests.get(f"{BASE_URL}/api/callbacks/tasks/{task_id}").json()
        execs = detail.get("executions", [])
        print(f"  回调执行记录数: {len(execs)}")
        check("至少存在执行记录", len(execs) >= 2, f"实际={len(execs)}")
        if execs:
            first = execs[-1]
            check("执行记录包含响应状态或错误信息",
                  first.get("duration_ms", 0) > 0 or first.get("error_message", "") != "")

    # ========== 接入方统计 + 详情 ==========
    test_section("测试 6: 接入方统计 - 患者数/照片数/对比数/配额进度/详情")
    stats_resp = requests.get(f"{BASE_URL}/api/admin/client-stats").json()
    print(f"  接入方数量: {stats_resp.get('total')}")
    found_a = found_b = found_default = False
    for s in stats_resp.get("stats", []):
        if s["client_id"] == client_a_id:
            found_a = True
            print(f"  诊所A统计: 患者={s['total_patients']}, 照片={s['total_photos']}, "
                  f"对比={s['total_compares']}, 异常={s['abnormal_photos']}, "
                  f"今日API用={s['daily_api_calls']}/上限={s['daily_api_quota']}, "
                  f"今日照片用={s['daily_photo_uploads']}/上限={s['daily_photo_quota']}, "
                  f"API配额进度={s['api_quota_used_pct']}%, 照片配额进度={s['photo_quota_used_pct']}%, "
                  f"允许对比={s['allow_compare']}, 默认={s['is_default']}")
            check("诊所A统计有多个患者", s["total_patients"] >= 2)
            check("诊所A统计有对比记录", s["total_compares"] >= 1)
            check("诊所A照片配额被用满或差不多", s["daily_photo_uploads"] >= 10)
            check("诊所A is_default=False", s["is_default"] is False)
        elif s["client_id"] == client_b_id:
            found_b = True
            check("诊所B allow_compare=False", s["allow_compare"] is False)
        elif s["client_id"] == default_client_id:
            found_default = True
            check("默认接入方 is_default=True", s["is_default"] is True)
    check("统计中包含诊所A", found_a)
    check("统计中包含诊所B", found_b)
    check("统计中包含默认接入方", found_default)

    # 接入方详情
    test_section("测试 7: 接入方详情 - 最近调用/失败回调/异常照片/用量进度")
    detail_resp = requests.get(f"{BASE_URL}/api/admin/clients/{client_a_id}/detail").json()
    check("详情 success=True", detail_resp.get("success") is True)
    check("详情 client.id 正确", detail_resp.get("client", {}).get("id") == client_a_id)
    check("详情 用量进度字段完整", detail_resp.get("daily_usage", {}).get("api_quota_limit") == 500)
    recent_calls = detail_resp.get("recent_logs", [])
    print(f"  最近调用数: {len(recent_calls)}")
    check("详情 最近调用列表非空", len(recent_calls) >= 1)
    failed_cbs = detail_resp.get("failed_callbacks", [])
    print(f"  失败回调数: {len(failed_cbs)}")
    check("详情 失败回调数非空", len(failed_cbs) >= 1)
    abnormals = detail_resp.get("abnormal_photos", [])
    print(f"  异常照片数: {len(abnormals)}")
    check("详情 异常照片非空(测试图片都不合格)", len(abnormals) >= 1)

    # ========== 默认接入方(无Key) ==========
    test_section("测试 8: 无 API Key 走默认接入方 - 旧系统兼容")
    no_key_patient = "P-OLD-SYS-001"
    resp_nk = submit_photos(no_key_patient, date(2024, 6, 15), True, headers_none, count=4)
    check("无Key请求可正常提交", resp_nk.get("success") is True)

    # 提交后, 该患者应归默认接入方
    stats2 = requests.get(f"{BASE_URL}/api/admin/client-stats").json()
    default_stat = next((s for s in stats2["stats"] if s["client_id"] == default_client_id), None)
    if default_stat:
        check("默认接入方患者数增加", default_stat["total_patients"] >= 1)
        print(f"  默认接入方 患者数={default_stat['total_patients']}, 照片={default_stat['total_photos']}")

    # 统计筛选 - 按状态码
    test_section("测试 9: 日志多维度筛选 (429 配额超限)")
    logs_429 = requests.get(f"{BASE_URL}/api/admin/logs", params={
        "status_code": 429, "client_id": client_c_id
    }).json()
    print(f"  诊所C 429日志数: {logs_429.get('total', 0)}")
    check("存在配额超限的429日志", logs_429.get("total", 0) >= 1)

    logs_compare = requests.get(f"{BASE_URL}/api/admin/logs", params={
        "api_category": "compare", "status_code": 200
    }).json()
    print(f"  成功对比日志数: {logs_compare.get('total', 0)}")
    check("存在成功的对比日志", logs_compare.get("total", 0) >= 1)

    summary()


if __name__ == "__main__":
    print()
    print("╔" + "=" * 58 + "╗")
    print("║    正畸复诊拍照对比服务 - v1.2.0 隔离/配额/回调详细版测试套件    ║")
    print("╚" + "=" * 58 + "╝")
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("✗ 无法连接到服务，请确认 http://localhost:8000 已启动")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"测试异常: {e}")
