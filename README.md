# DeadPod

A naive way to get ads out of your podcast stream.

To add a podcast you can just `https://[yourdomain]/rss/[url]`
and you'll get a feed containing ads stripped.

When downloading the podcast there will be a delay of ~30 seconds
per hour of podcast content to filter out ads.

## Run

```shell
docker-compose up -d
```