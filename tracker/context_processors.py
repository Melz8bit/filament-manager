def theme(request):
    return {"dark_mode": request.session.get("theme") == "dark"}
