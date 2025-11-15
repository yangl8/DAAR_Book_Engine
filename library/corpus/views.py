from django.shortcuts import render

from corpus.backend.search_service import SearchService


from corpus.backend.recommendations import RecommendationService

from django.views.decorators.http import require_GET
from django.http import JsonResponse
def search_view(request):
    quick_links = [
        {
            "label": "Find books",
            "description": "Browse the Gutenberg catalogue",
            "url": "https://www.gutenberg.org/ebooks/",
            "external": True,
        },
        {
            "label": "The Gutenberg project",
            "description": "Project background and licensing",
            "url": "https://www.gutenberg.org/about/",
            "external": True,
        },
        {
            "label": "DAAR",
            "description": "Course resources and schedule",
            "url": "https://www-npa.lip6.fr/~buixuan/daar2025",
            "external": True,
        },
        {
            "label": "Repository",
            "description": "Project source code on GitHub",
            "url": "https://github.com/yangl8/DAAR_Book_Engine",
            "external": True,
        },
    ]

    search_modes = [
        {"value": "simple", "label": "Keyword"},
        {"value": "regex", "label": "Regex"},
        {"value": "graph", "label": "Graph ranking"},
    ]

    ranking_options = [
        {"value": "default", "label": "Relevance"},
        {"value": "pagerank", "label": "PageRank"},
        {"value": "closeness", "label": "Closeness"},
        {"value": "betweenness", "label": "Betweenness"},
    ]

    context = {
        "api_base": "/api",
        "quick_links": quick_links,
        "search_modes": search_modes,
        "ranking_options": ranking_options,
        "initial_query": request.GET.get("q", "").strip(),
        "initial_mode": request.GET.get("mode", "simple"),
        "initial_order": request.GET.get("order", "default"),
    }
    return render(request, "search.html", context)

#search context
import time

def search_api(request):
    """
    GET /api/search?q=love&order=pagerank
    """
    query = request.GET.get("q", "").strip()
    order = request.GET.get("order", "total")   # 前端用的是 order，不是 centrality

    start = time.time()
    results = SearchService.search(query, centrality=order, limit=20)
    elapsed = (time.time() - start) * 1000.0

    data = {
        "total": len(results),   # 前端用 data.total
        "elapsed_ms": elapsed,   # 前端用 data.elapsed_ms
        "results": results,      # ⭐ 这里是 list，前端才能 .length
    }
    return JsonResponse(data)





@require_GET
def recommendations_query_view(request):
    """
    GET /api/recommendations/query?q=...&limit=6
    Frontend expects: {"items": [...]}
    """
    q = request.GET.get("q", "").strip()

    try:
        limit = int(request.GET.get("limit", 6))
    except:
        limit = 6

    limit = max(1, min(limit, 20))

    # 原始推荐结果
    raw_results = RecommendationService.recommend_for_query(query=q, limit=limit)
    # raw_results 是类似：
    # [{"book_id": ..., "title": ..., "similarity": 0.32, "total": 0.55, "pagerank": ...}, ...]

    items = []
    for r in raw_results:
        items.append({
            "book_id": r.get("book_id"),
            "title": r.get("title"),
            # 推荐理由你可以选择 similarity、pagerank、total 中任意一个
            "reason": f"similarity: {r.get('similarity', 0):.3f}"
        })

    return JsonResponse({"items": items})
