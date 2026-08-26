<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:media="http://search.yahoo.com/mrss/"
  xmlns:bili="urn:bilibili-rss:metrics"
  exclude-result-prefixes="media bili">
  <xsl:output method="html" encoding="UTF-8" omit-xml-declaration="yes"/>
  <xsl:template match="/rss/channel">
    <html lang="zh-CN">
      <head>
        <meta charset="UTF-8"/>
        <meta name="viewport" content="width=device-width, initial-scale=1"/>
        <title><xsl:value-of select="title"/></title>
        <style>
          :root { color-scheme: light dark; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
          body { margin: 0; background: #f5f7fb; color: #172033; }
          main { max-width: 920px; margin: 0 auto; padding: 36px 20px 64px; }
          header { background: white; border: 1px solid #e3e8f0; border-radius: 8px; padding: 24px; margin-bottom: 16px; }
          h1 { margin: 0 0 8px; font-size: 26px; }
          p { color: #667085; line-height: 1.6; }
          .meta { font-size: 13px; color: #667085; }
          .metrics { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 10px 0; color: #475467; font-size: 13px; }
          .metric { white-space: nowrap; }
          article { display: grid; grid-template-columns: 180px 1fr; gap: 18px; background: white; border: 1px solid #e3e8f0; border-radius: 8px; padding: 16px; margin: 12px 0; }
          img { width: 180px; aspect-ratio: 16 / 10; object-fit: cover; border-radius: 6px; background: #e9edf4; }
          h2 { margin: 0 0 8px; font-size: 18px; }
          a { color: #1769e0; text-decoration: none; }
          a:hover { text-decoration: underline; }
          .description { white-space: pre-line; }
          @media (max-width: 640px) { article { grid-template-columns: 1fr; } img { width: 100%; } }
          @media (prefers-color-scheme: dark) { body { background: #111827; color: #eef2ff; } header, article { background: #1f2937; border-color: #374151; } p, .meta, .metrics { color: #aab4c4; } }
        </style>
      </head>
      <body>
        <main>
          <header>
            <h1><xsl:value-of select="title"/></h1>
            <p><xsl:value-of select="description"/></p>
            <div class="meta">更新：<xsl:value-of select="lastBuildDate"/> · <xsl:value-of select="count(item)"/> 条视频</div>
          </header>
          <xsl:for-each select="item">
            <article>
              <div>
                <xsl:if test="media:thumbnail/@url"><img src="{media:thumbnail/@url}" alt="" referrerpolicy="no-referrer"/></xsl:if>
              </div>
              <div>
                <h2><a href="{link}"><xsl:value-of select="title"/></a></h2>
                <div class="meta"><xsl:value-of select="pubDate"/></div>
                <xsl:if test="bili:viewCount or bili:danmakuCount or bili:commentCount or bili:likeCount or bili:coinCount or bili:favoriteCount or bili:shareCount">
                  <div class="metrics">
                    <xsl:if test="bili:viewCount"><span class="metric">播放 <xsl:value-of select="format-number(number(bili:viewCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:danmakuCount"><span class="metric">弹幕 <xsl:value-of select="format-number(number(bili:danmakuCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:commentCount"><span class="metric">评论 <xsl:value-of select="format-number(number(bili:commentCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:likeCount"><span class="metric">点赞 <xsl:value-of select="format-number(number(bili:likeCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:coinCount"><span class="metric">投币 <xsl:value-of select="format-number(number(bili:coinCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:favoriteCount"><span class="metric">收藏 <xsl:value-of select="format-number(number(bili:favoriteCount), '#,##0')"/></span></xsl:if>
                    <xsl:if test="bili:shareCount"><span class="metric">分享 <xsl:value-of select="format-number(number(bili:shareCount), '#,##0')"/></span></xsl:if>
                  </div>
                </xsl:if>
                <p class="description"><xsl:value-of select="description"/></p>
                <a href="{link}">前往 Bilibili</a>
              </div>
            </article>
          </xsl:for-each>
        </main>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
