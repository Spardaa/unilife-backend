import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.scheduler.background_tasks import BackgroundTaskScheduler

async def mock_worker(worker_id: int, lock_key: str, results: list):
    """模拟一个后端的 Worker 尝试抢锁"""
    scheduler = BackgroundTaskScheduler()
    
    # 模拟大家都在同一时刻（毫秒级）并发触发
    # 对于带有锁的场景，第一抢到的应该成功，其他的全失败
    print(f"[Worker {worker_id}] 准备并发抢锁: {lock_key}")
    
    # asyncio.sleep(0) 强制交出控制权，让所有 worker 排队在起跑区并尽可能高保真模拟并发调用
    await asyncio.sleep(0) 
    
    # 因为 _acquire_scheduler_lock 不是 async, 我们需要把它跑在执行器里以免阻塞 event loop 测试
    # 但由于它内部就是普通的 sqlalchemy 同步操作，这里做测试可以直接调用
    loop = asyncio.get_event_loop()
    acquired = await loop.run_in_executor(None, scheduler._acquire_scheduler_lock, lock_key)
    
    if acquired:
        print(f"✅ [Worker {worker_id}] ---- 抢锁成功！将拉起 LLM 发送推送 ----")
    else:
        print(f"❌ [Worker {worker_id}] 抢锁失败，发现兄弟进程正在处理。跳过。")
        
    results.append((worker_id, acquired))

async def main():
    print("====== 开始多 Worker 并发事件倒计时锁测试 ======\n")
    
    # 构建一个假的事件提醒锁（例如某事件距离发生还有 15 分钟）
    event_id = "test_event_2026_02_25"
    event_start_str = "202602251200"
    lock_key = f"event_reminder:{event_id}:{event_start_str}"
    print(f"构造锁 ID: {lock_key}\n")
    
    results = []
    
    # 模拟 4 个 Gunicorn/Uvicorn Worker 在同一个毫秒内执行 
    tasks = [mock_worker(i, lock_key, results) for i in range(1, 5)]
    
    # 让这 4 个 worker 高并发同时飙车起跑
    await asyncio.gather(*tasks)
    
    print("\n====== 最终结果汇总 ======")
    success_count = sum(1 for r in results if r[1])
    fail_count = sum(1 for r in results if not r[1])
    print(f"总计试图并发进程: 4")
    print(f"最终真正请求 LLM 发通知数量: {success_count} (预期只应该是 1)")
    print(f"成功被拦截的安全拦截次数:   {fail_count} (预期应该是 3)")
    
    if success_count == 1 and fail_count == 3:
        print("\n🎉 测试完美通过！100% 杜绝了连发 4 条同一时间点推送的漏洞。")
    else:
        print("\n⚠️ 测试没按预期工作！需要重新排查代码。")

if __name__ == "__main__":
    asyncio.run(main())
