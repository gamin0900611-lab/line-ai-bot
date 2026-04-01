import requests


def web_search(query):

    try:

        url = "https://api.duckduckgo.com/"

        params = {
            "q": query,
            "format": "json"
        }

        res = requests.get(url, params=params)

        data = res.json()

        if "AbstractText" in data and data["AbstractText"]:
            return data["AbstractText"]

        if "RelatedTopics" in data and len(data["RelatedTopics"]) > 0:

            results = []

            for topic in data["RelatedTopics"][:3]:

                if "Text" in topic:
                    results.append(topic["Text"])

            return "\n".join(results)

        return "沒有找到相關資訊"

    except Exception as e:

        print("Web search error:", e)

        return "搜尋失敗"
