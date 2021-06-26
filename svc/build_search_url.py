from otokuna.dumping import build_search_url


def main(event, context):
    ward = event["batch_name"]
    event["search_url"] = build_search_url(building_categories=("マンション",),
                                           wards=(ward,), only_today=True)
    return event
