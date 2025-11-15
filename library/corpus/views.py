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
    # === 2) 按书名搜索 ===
    elif mode == "title":
        results = SearchService.search_by_title(
            query=q,
            centrality=order,
            limit=20,
        )
    # === 3) 按作者搜索 ===
    elif mode == "author":
        results = SearchService.search_by_author(
            query=q,
            centrality=order,
            limit=20,
        )
    else:
        # normal & graph search
        results = SearchService.search(
            query=q,
            centrality=order,
            limit=20
        )

    base_url = "https://www.gutenberg.org/ebooks/"
    for r in results:
        book_id = r.get("book_id")
        if book_id is not None:
            r["gutenberg_url"] = f"{base_url}{book_id}"

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

    # 推荐结果（后端已有逻辑）
    raw_results = RecommendationService.recommend_for_query(query=q, limit=limit)

    base_url = "https://www.gutenberg.org/ebooks/"

    items = []
    for r in raw_results:
        # 先取出 book_id 和 similarity
        book_id = r.get("book_id")
        similarity = float(r.get("similarity", 0.0) or 0.0)

        items.append({
            "book_id": book_id,
            "title": r.get("title"),
            # 推荐理由
            "reason": f"similarity: {similarity:.3f}",
            # 只有 book_id 不为空时拼接链接
            "gutenberg_url": f"{base_url}{book_id}" if book_id is not None else None,
        })

    return JsonResponse({"items": items})

