from django.shortcuts import render

from corpus.backend.search_service import SearchService
from corpus.backend.recommendations import RecommendationService
from corpus.backend.regex_search_service import RegexSearchService
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
        {"value": "title", "label": "Title"},
        {"value": "author", "label": "Author"},
        {"value": "keywords", "label": "Keywords"},
        {"value": "regex", "label": "Regex"},
    ]

    ranking_options = [
        {"value": "default", "label": "Comprehensive"},
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
        "initial_mode": request.GET.get("mode", "keywords"),
        "initial_order": request.GET.get("order", "default"),
    }
    return render(request, "search.html", context)
@require_GET
def search_api(request):
    """
    Unified search endpoint supporting:
    - mode=keywords (default full-text search)
    - mode=title / author (field-specific search, handled by SearchService)
    - mode=regex (pattern match via RegexSearchService)
    """
    q = request.GET.get("q", "").strip()
    mode = request.GET.get("mode", "keywords")
    order = request.GET.get("order", "default")

    import time
    start = time.time()

    # === regex search ===
    if mode == "regex":
        results = RegexSearchService.search(
            pattern=q,
            centrality=order,
            limit=20
        )
    else:
        # normal & graph search
        results = SearchService.search(
            query=q,
            centrality=order,
            limit=20
        )

    elapsed = (time.time() - start) * 1000.0

    return JsonResponse({
        "total": len(results),
        "elapsed_ms": elapsed,
        "results": results,
    })

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
