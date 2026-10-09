"""dlt resource raw_tweets: menulis hasil TextSource X ke raw (bagian 4.2).

Transformasi dan pemilihan ticker ada di TextSource dan flow. Resource ini hanya meneruskan baris.
"""

import dlt


@dlt.resource(
    name="raw_tweets",
    write_disposition="append",
    primary_key="tweet_id",
    max_table_nesting=0,
)
def raw_tweets(items: list[dict]):
    if items:
        yield items
