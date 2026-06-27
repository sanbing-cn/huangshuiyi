import scala.io.Source
import scala.collection.mutable

object tangshi{

  def main(args: Array[String]): Unit = {
    println("=" * 80)
    println("唐诗数据分析系统")
    println("=" * 80)

    val filePath = "中文分词/唐诗.txt"
    val poems = loadPoemsFromClasspath(filePath)

    println(s"\n共加载 ${poems.size} 首唐诗\n")

    // 1. 基本统计信息
    basicStatistics(poems)

    // 2. 诗人统计分析
    poetAnalysis(poems)

    // 3. 高频词分析 TOP30
    highFrequencyWords(poems, 30)

    // 4. 季节词汇分析
    seasonAnalysis(poems)

    // 5. 情感词汇分析
    emotionAnalysis(poems)

    // 6. 常用意象词汇分析
    imageryAnalysis(poems)

    // 7. 主题分布分析
    themeAnalysis(poems)

    // 8. 杜甫诗歌风格分析
    specificPoetStyleAnalysis(poems, "杜甫")

    // 9. 符合当下意境的诗歌推荐
    recommendPoems(poems)
  }

  def loadPoemsFromClasspath(resourceName: String): List[Poem] = {
    println(s"尝试加载资源文件: $resourceName")

    var stream = getClass.getClassLoader.getResourceAsStream(resourceName)

    if (stream == null) {
      stream = getClass.getResourceAsStream("/" + resourceName)
    }

    if (stream == null) {
      stream = getClass.getResourceAsStream(resourceName)
    }

    if (stream == null) {
      println(s"错误：无法找到资源文件: $resourceName")
      throw new RuntimeException(s"无法找到资源文件: $resourceName")
    }

    println(s"成功加载资源文件")
    val source = scala.io.Source.fromInputStream(stream, "UTF-8")
    val lines = source.getLines().toList
    source.close()

    println(s"文件总行数: ${lines.length}")

    val poems = mutable.ListBuffer[Poem]()
    var i = 0

    while (i < lines.length) {
      val line = lines(i).trim

      if (line.contains("卷") && line.contains("【") && line.contains("】")) {
        val titleStart = line.indexOf("【")
        val titleEnd = line.indexOf("】")

        if (titleStart != -1 && titleEnd != -1 && titleEnd > titleStart) {
          // 提取【】之间的内容，例如："晓发公安（数月憩息此县）】杜甫" 中的 "晓发公安（数月憩息此县）"
          val titleContent = line.substring(titleStart + 1, titleEnd)

          // 在整行中查找】后面的作者名
          val afterTitleBracket = line.substring(titleEnd + 1).trim

          val (title, author) = if (afterTitleBracket.nonEmpty) {
            (titleContent.trim, afterTitleBracket.trim)
          } else {
            // 如果】后面没有内容，尝试从titleContent中提取
            val lastSpaceIndex = titleContent.lastIndexOf(" ")
            if (lastSpaceIndex != -1 && lastSpaceIndex < titleContent.length - 1) {
              (titleContent.substring(0, lastSpaceIndex).trim,
                titleContent.substring(lastSpaceIndex + 1).trim)
            } else {
              (titleContent.trim, "未知")
            }
          }

          val contentLines = mutable.ListBuffer[String]()
          i += 1
          var continueReading = true

          while (i < lines.length && continueReading) {
            val nextLine = lines(i).trim

            if (nextLine.contains("卷") && nextLine.contains("【") && nextLine.contains("】")) {
              continueReading = false
            } else {
              if (nextLine.nonEmpty) {
                contentLines += nextLine
              }
              i += 1
            }
          }

          val content = contentLines.mkString("")
          if (content.nonEmpty && content.length > 5) {
            poems += Poem(title, author, content)
            if (poems.size <= 5) {
              println(s"示例 ${poems.size}: 《$title》 - 作者:$author, 内容长度:${content.length}")
            }
          }
        } else {
          i += 1
        }
      } else {
        i += 1
      }
    }

    println(s"\n解析完成，共加载 ${poems.size} 首诗歌")
    if (poems.nonEmpty) {
      val authors = poems.map(_.author).distinct
      println(s"识别到的诗人数量: ${authors.size}")
      println(s"前10位诗人: ${authors.take(10).mkString(", ")}")
    }
    poems.toList
  }

  def loadPoems(filePath: String): List[Poem] = {
    val source = Source.fromFile(filePath, "UTF-8")
    val lines = source.getLines().toList
    source.close()

    val poems = mutable.ListBuffer[Poem]()
    var i = 0

    while (i < lines.length) {
      val line = lines(i).trim

      if (line.contains("卷") && line.contains("【")) {
        val titleStart = line.indexOf("【")
        val titleEnd = line.indexOf("】")

        if (titleStart != -1 && titleEnd != -1) {
          val fullTitle = line.substring(titleStart + 1, titleEnd)
          val parts = fullTitle.split("】").headOption.getOrElse(fullTitle)

          val titleInfo = line.substring(titleStart + 1, titleEnd)
          val lastSpaceIndex = titleInfo.lastIndexOf(" ")

          val (title, author) = if (lastSpaceIndex != -1) {
            (titleInfo.substring(0, lastSpaceIndex),
              titleInfo.substring(lastSpaceIndex + 1))
          } else {
            (titleInfo, "未知")
          }

          val contentLines = mutable.ListBuffer[String]()
          i += 1
          var continueReading = true

          while (i < lines.length && continueReading) {
            val nextLine = lines(i).trim
            if (nextLine.isEmpty || (nextLine.contains("卷") && nextLine.contains("【"))) {
              continueReading = false
            } else if (nextLine.nonEmpty && !nextLine.startsWith("卷")) {
              contentLines += nextLine
            }
            i += 1
          }

          val content = contentLines.mkString("")
          if (content.nonEmpty) {
            poems += Poem(title, author, content)
          }
        }
      }
      i += 1
    }

    poems.toList
  }
  // 1. 基本统计信息
  def basicStatistics(poems: List[Poem]): Unit = {
    println("=" * 80)
    println("一、唐诗基本统计信息")
    println("=" * 80)

    if (poems.isEmpty) {
      println("警告：未加载到任何诗歌数据！")
      println("请检查资源文件路径是否正确。")
      return
    }

    val totalPoems = poems.size
    val authors = poems.map(_.author).distinct
    val totalAuthors = authors.size

    val poemLengths = poems.map(_.content.length)
    val avgLength = poemLengths.sum.toDouble / poemLengths.size
    val maxLength = poemLengths.max
    val minLength = poemLengths.min

    val longestPoem = poems.find(_.content.length == maxLength)
    val shortestPoem = poems.find(_.content.length == minLength)

    println(f"诗歌总数: $totalPoems 首")
    println(f"诗人数量: $totalAuthors 位")
    println(f"平均字数: $avgLength%.2f 字")
    println(f"最长诗歌: $maxLength 字 - ${longestPoem.map(_.title).getOrElse("")}")
    println(f"最短诗歌: $minLength 字 - ${shortestPoem.map(_.title).getOrElse("")}")

    val topPoets = poems.groupBy(_.author)
      .mapValues(_.size)
      .toList
      .sortBy(-_._2)
      .take(10)

    println("\n创作数量最多的前10位诗人:")
    topPoets.zipWithIndex.foreach { case ((author, count), idx) =>
      println(f"  ${idx + 1}. $author: $count 首")
    }
  }
  // 2. 诗人统计分析
  def poetAnalysis(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("二、诗人深度分析")
    println("=" * 80)

    val poetGroups = poems.groupBy(_.author)

    println("\n各时期代表诗人及其作品特点:")

    val topPoets = poetGroups.mapValues(_.size).toList.sortBy(-_._2).take(5)

    topPoets.foreach { case (author, count) =>
      println(s"\n【$author】")
      println(s"  作品数量: $count 首")

      val poetPoems = poetGroups(author)
      val avgLength = poetPoems.map(_.content.length).sum.toDouble / count

      val allWords = segmentText(poetPoems.map(_.content).mkString(""))
      val wordFreq = allWords.groupBy(identity).mapValues(_.size).toList.sortBy(-_._2).take(10)

      println(f"  平均篇幅: $avgLength%.2f 字")
      println(s"  常用词汇: ${wordFreq.map(_._1).take(5).mkString("、")}")
    }
  }

  // 3. 高频词分析
  def highFrequencyWords(poems: List[Poem], topN: Int): Unit = {
    println("\n" + "=" * 80)
    println(s"三、全唐诗高频词汇 TOP$topN")
    println("=" * 80)

    val allContent = poems.map(_.content).mkString("")
    val words = segmentText(allContent)

    val stopWords = Set("之", "乎", "者", "也", "而", "其", "以", "于", "为", "有",
      "不", "人", "中", "大", "上", "下", "是", "在", "我", "之",
      " ", "\u3000", "", "一", "何", "无", "不", "未", "已", "复",
      "自", "相", "所", "此", "亦", "皆", "俱", "犹", "尚", "方")

    val filteredWords = words.filterNot(stopWords.contains).filter(_.length >= 1)
    val wordFreq = filteredWords.groupBy(identity).mapValues(_.size).toList.sortBy(-_._2)

    println("排名\t词汇\t出现次数\t频率(%)")
    println("-" * 60)

    val total = filteredWords.size
    wordFreq.take(topN).zipWithIndex.foreach { case ((word, count), idx) =>
      val frequency = count.toDouble / total * 100
      println(f"${idx + 1}\t$word\t$count\t$frequency%.4f%%")
    }
  }

  // 4. 季节词汇分析
  def seasonAnalysis(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("四、季节词汇分析")
    println("=" * 80)

    val seasonWords = Map(
      "春" -> List("春", "花", "柳", "桃", "燕", "草", "绿", "青", "东风", "春风", "春雨", "花开", "春色", "春光"),
      "夏" -> List("夏", "荷", "莲", "蝉", "暑", "热", "雨", "雷", "炎热", "荷花", "夏日", "绿树"),
      "秋" -> List("秋", "月", "霜", "雁", "菊", "落叶", "秋风", "秋雨", "秋月", "寒", "凉", "萧瑟"),
      "冬" -> List("冬", "雪", "冰", "寒", "冷", "梅", "北风", "雪花", "寒冬", "冰雪", "朔风", "岁暮")
    )

    val allContent = poems.map(_.content).mkString("")

    println("\n各季节相关词汇出现频次:")
    println("-" * 60)

    seasonWords.foreach { case (season, words) =>
      val count = words.map(word => allContent.sliding(word.length).count(_ == word)).sum
      println(f"  $season 季: $count 次")
    }

    println("\n季节性诗歌示例:")

    poems.filter(p => p.content.contains("春") || p.content.contains("花")).take(3).foreach { poem =>
      println(s"\n  《${poem.title}》 - ${poem.author}")
      println(s"  ${poem.content.take(50)}...")
    }
  }

  // 5. 情感词汇分析
  def emotionAnalysis(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("五、情感词汇分析")
    println("=" * 80)

    if (poems.isEmpty) {
      println("警告：没有诗歌数据可供分析")
      return
    }

    val emotionCategories = Map(
      "喜悦" -> List("喜", "乐", "欢", "笑", "醉", "歌", "畅", "欣", "悦", "怡"),
      "悲伤" -> List("悲", "哭", "泪", "愁", "哀", "伤", "痛", "苦", "怨", "恨"),
      "思念" -> List("思", "念", "忆", "怀", "望", "想", "梦", "归", "别", "离"),
      "孤独" -> List("孤", "独", "寂", "寞", "单", "只", "空", "幽", "静", "闲"),
      "豪情" -> List("壮", "豪", "雄", "剑", "酒", "马", "战", "功", "名", "志")
    )

    val allContent = poems.map(_.content).mkString("")

    println("\n各类情感词汇出现频次:")
    println("-" * 60)

    emotionCategories.foreach { case (emotion, words) =>
      val count = words.map(word => allContent.sliding(word.length).count(_ == word)).sum
      val barLength = if (count >= 10) count / 10 else 0
      val bar = "█" * barLength
      println(f"  $emotion: $count%5d 次 $bar")
    }

    println("\n情感倾向分析:")
    val positiveCount = emotionCategories("喜悦").map(w => allContent.sliding(w.length).count(_ == w)).sum
    val negativeCount = emotionCategories("悲伤").map(w => allContent.sliding(w.length).count(_ == w)).sum
    val nostalgicCount = emotionCategories("思念").map(w => allContent.sliding(w.length).count(_ == w)).sum

    println(f"  积极情感: $positiveCount 次")
    println(f"  消极情感: $negativeCount 次")
    println(f"  思乡怀旧: $nostalgicCount 次")

    if (positiveCount > negativeCount) {
      println("  整体倾向: 积极向上")
    } else {
      println("  整体倾向: 略带忧伤")
    }
  }

  // 6. 常用意象词汇分析
  def imageryAnalysis(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("六、常用意象词汇使用频率")
    println("=" * 80)

    val imageryCategories = Map(
      "自然景物" -> List("山", "水", "云", "月", "风", "雨", "雪", "日", "星", "天", "江", "河", "湖", "海"),
      "植物" -> List("花", "柳", "松", "竹", "梅", "兰", "菊", "桃", "李", "草", "叶", "树"),
      "动物" -> List("鸟", "雁", "鹤", "马", "鱼", "蝉", "蝶", "莺", "燕", "龙", "凤"),
      "建筑" -> List("楼", "亭", "台", "阁", "寺", "庙", "城", "门", "窗", "桥", "船", "舟"),
      "器物" -> List("剑", "酒", "琴", "书", "灯", "烛", "镜", "钟", "鼓", "旗", "衣", "帽"),
      "人物" -> List("君", "客", "友", "僧", "仙", "王", "侯", "将", "士", "农", "渔", "樵")
    )

    val allContent = poems.map(_.content).mkString("")

    println("\n各类意象使用频次统计:")
    println("-" * 60)

    val imageryStats = imageryCategories.map { case (category, words) =>
      val count = words.map(word => allContent.sliding(word.length).count(_ == word)).sum
      (category, count, words)
    }.toList.sortBy(-_._2)

    imageryStats.foreach { case (category, count, words) =>
      println(s"\n  【$category】总计: $count 次")
      val wordCounts = words.map(w => (w, allContent.sliding(w.length).count(_ == w)))
        .sortBy(-_._2).take(5)
      wordCounts.foreach { case (word, c) =>
        println(f"    $word: $c 次")
      }
    }
  }

  // 7. 主题分布分析
  def themeAnalysis(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("七、诗歌主题分布分析")
    println("=" * 80)

    if (poems.isEmpty) {
      println("警告：没有诗歌数据可供分析")
      return
    }

    val themeKeywords = Map(
      "山水田园" -> List("山", "水", "田", "园", "村", "野", "林", "泉", "石", "溪"),
      "边塞战争" -> List("战", "兵", "军", "塞", "边", "征", "戎", "胡", "虏", "关"),
      "送别怀人" -> List("送", "别", "离", "归", "去", "来", "远", "近", "逢", "遇"),
      "咏史怀古" -> List("古", "今", "昔", "旧", "新", "往", "来", "千", "百", "年"),
      "爱情闺怨" -> List("情", "爱", "思", "梦", "妆", "眉", "颜", "妾", "君", "郎"),
      "哲理感悟" -> List("道", "理", "心", "性", "真", "假", "有", "无", "生", "死"),
      "饮酒作乐" -> List("酒", "饮", "醉", "杯", "壶", "觞", "酌", "酣", "酿", "醇"),
      "忧国忧民" -> List("国", "民", "君", "臣", "朝", "政", "治", "乱", "安", "危")
    )

    val themeCounts = themeKeywords.map { case (theme, keywords) =>
      val count = poems.count { poem =>
        keywords.exists(keyword => poem.content.contains(keyword))
      }
      (theme, count)
    }.toList.sortBy(-_._2)

    println("\n各主题诗歌数量分布:")
    println("-" * 60)

    val maxCount = themeCounts.map(_._2).max
    themeCounts.foreach { case (theme, count) =>
      val percentage = count.toDouble / poems.size * 100
      val barLength = if (maxCount > 0) count * 40 / maxCount else 0
      val bar = "█" * barLength
      println(f"  $theme%-12s: $count%4d 首 ($percentage%5.2f%%) $bar")
    }
  }

  // 8. 特定诗人风格分析
  def specificPoetStyleAnalysis(poems: List[Poem], poetName: String): Unit = {
    println("\n" + "=" * 80)
    println(s"八、${poetName}诗歌风格分析")
    println("=" * 80)

    val poetPoems = poems.filter(_.author == poetName)

    if (poetPoems.isEmpty) {
      println(s"未找到 ${poetName} 的诗歌")
      return
    }

    println(s"\n作品总数: ${poetPoems.size} 首")

    val allContent = poetPoems.map(_.content).mkString("")
    val words = segmentText(allContent)

    val stopWords = Set("之", "乎", "者", "也", "而", "其", "以", "于", "为", "有",
      "不", "人", "中", "大", "上", "下", "是", "在", "我")

    val filteredWords = words.filterNot(stopWords.contains).filter(_.length >= 1)
    val wordFreq = filteredWords.groupBy(identity).mapValues(_.size).toList.sortBy(-_._2).take(20)

    println("\n个人常用词汇 TOP20:")
    wordFreq.zipWithIndex.foreach { case ((word, count), idx) =>
      println(f"  ${idx + 1}. $word: $count 次")
    }

    val avgLength = poetPoems.map(_.content.length).sum.toDouble / poetPoems.size
    println(f"\n平均篇幅: $avgLength%.2f 字")

    println("\n代表作品:")
    poetPoems.take(5).foreach { poem =>
      println(s"\n  《${poem.title}》")
      val preview = if (poem.content.length > 60) poem.content.take(60) + "..." else poem.content
      println(s"  $preview")
    }
  }

  // 9. 推荐符合当下意境的诗歌
  def recommendPoems(poems: List[Poem]): Unit = {
    println("\n" + "=" * 80)
    println("九、符合当下意境的诗歌推荐")
    println("=" * 80)

    println("\n【春日意境】")
    val springPoems = poems.filter(p =>
      p.content.contains("春") && (p.content.contains("花") || p.content.contains("柳"))
    ).take(3)

    springPoems.foreach { poem =>
      println(s"\n  《${poem.title}》 - ${poem.author}")
      println(s"  ${poem.content.take(80)}...")
    }

    println("\n\n【秋日意境】")
    val autumnPoems = poems.filter(p =>
      p.content.contains("秋") && (p.content.contains("月") || p.content.contains("霜"))
    ).take(3)

    autumnPoems.foreach { poem =>
      println(s"\n  《${poem.title}》 - ${poem.author}")
      println(s"  ${poem.content.take(80)}...")
    }

    println("\n\n【离别意境】")
    val farewellPoems = poems.filter(p =>
      p.content.contains("别") || p.content.contains("送")
    ).take(3)

    farewellPoems.foreach { poem =>
      println(s"\n  《${poem.title}》 - ${poem.author}")
      println(s"  ${poem.content.take(80)}...")
    }
  }

  // 中文分词
  def segmentText(text: String): List[String] = {
    // 只保留中文字符，移除所有标点、数字、字母和空白
    text.filter(c => c >= '\u4e00' && c <= '\u9fff').map(_.toString).toList
  }
}

case class Poem(title: String, author: String, content: String)
