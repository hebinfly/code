import os
import re
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import html2text

def process_zhihu(collection_id, only_title_link=True, from_page=None, to_page=None):
    """
    知乎收藏夹下载工具
    
    参数:
    collection_id: 收藏夹ID (字符串)
    only_title_link: 是否只抓取标题和链接 (布尔值，默认为True)
    from_page: 起始页码 (整数，可选)
    to_page: 结束页码 (整数，可选)
    """
    # 配置信息
    ZHIHU_USERNAME = ""
    ZHIHU_PASSWORD = ""
    BASE_URL = f"https://www.zhihu.com/collection/{collection_id}"
    
    # 创建输出文件名
    output_suffix = "标题和链接" if only_title_link else "完整内容"
    
    # 确定页码范围描述
    if from_page is not None and to_page is not None:
        page_range = f"_{from_page}-{to_page}页"
        page_range_desc = f"从第{from_page}页到第{to_page}页"
    elif from_page is not None:
        page_range = f"_从{from_page}页开始"
        page_range_desc = f"从第{from_page}页开始"
        to_page = from_page  # 只抓取一页
    elif to_page is not None:
        page_range = f"_到{to_page}页"
        page_range_desc = f"到第{to_page}页结束"
        from_page = 1  # 从第一页开始
    else:
        page_range = "_全量"
        page_range_desc = "所有页面"
        from_page = 1
        to_page = 1000  # 设置一个较大的数
    
    OUTPUT_FILE = f"知乎收藏_{collection_id}{page_range}_{output_suffix}.txt"
    
    def init_driver():
        """初始化浏览器"""
        chrome_options = Options()
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        return webdriver.Chrome(options=chrome_options)
    
    def login(driver):
        """登录知乎"""
        print("启动浏览器登录知乎...")
        driver.maximize_window()
        driver.get("https://www.zhihu.com/signin")
        
        try:
            # 切换到密码登录
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.SignContainer-switch span'))
            ).click()
            time.sleep(1)
        except:
            print("无法点击登录方式切换，尝试继续")
        
        # 输入用户名
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, 'username'))
        )
        username_field.clear()
        username_field.send_keys(ZHIHU_USERNAME)
        
        # 输入密码
        password_field = driver.find_element(By.NAME, 'password')
        password_field.clear()
        password_field.send_keys(ZHIHU_PASSWORD)
        
        # 点击登录
        driver.find_element(By.CSS_SELECTOR, '.SignFlow-submitButton').click()
        
        # 等待登录成功
        try:
            WebDriverWait(driver, 15).until(
                lambda d: "www.zhihu.com" in d.current_url and "signin" not in d.current_url
            )
            print("登录成功!")
            return True
        except:
            print("登录失败或需要验证码")
            return False
    
    def get_page_items(driver, page_num):
        """获取指定页面的收藏项"""
        page_url = f"{BASE_URL}?page={page_num}"
        print(f"访问第 {page_num} 页: {page_url}")
        driver.get(page_url)
        
        # 等待页面加载
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".ContentItem"))
            )
            print(f"第 {page_num} 页加载成功")
        except TimeoutException:
            print(f"第 {page_num} 页加载超时，尝试继续")
            return []
        except Exception as e:
            print(f"第 {page_num} 页加载出错: {str(e)}")
            return []
        
        # 滚动加载当前页所有内容
        print("滚动加载页面内容...")
        last_height = driver.execute_script("return document.body.scrollHeight")
        scroll_attempts = 0
        
        while scroll_attempts < 3:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(random.uniform(0.5, 1.0))
            new_height = driver.execute_script("return document.body.scrollHeight")
            
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
                last_height = new_height
        
        # 获取当前页所有收藏项
        try:
            items = driver.find_elements(By.CSS_SELECTOR, ".ContentItem")
            print(f"第 {page_num} 页找到 {len(items)} 个收藏项")
            return items
        except Exception as e:
            print(f"获取收藏项失败: {str(e)}")
            return []
    
    def extract_title_and_link(item):
        """从收藏项中提取标题和链接"""
        try:
            # 提取标题元素
            title_element = item.find_element(By.CSS_SELECTOR, ".ContentItem-title a")
            title = title_element.text.strip()
            link = title_element.get_attribute("href")
            return title, link
        except:
            try:
                # 备选选择器
                title_element = item.find_element(By.CSS_SELECTOR, ".ContentItem-title")
                title = title_element.text.strip()
                link_element = item.find_element(By.CSS_SELECTOR, ".ContentItem-title a")
                link = link_element.get_attribute("href")
                return title, link
            except Exception as e:
                print(f"提取标题和链接失败: {str(e)}")
                return None, None
    
    def save_title_and_link(output_file, index, title, link):
        """保存标题和链接到文件"""
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{index}. {title}\n")
            f.write(f"链接: {link}\n")
            f.write("-" * 80 + "\n")
    
    def extract_text_content(html_content):
        """从HTML中提取纯文本内容"""
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取标题
        title = ""
        title_element = soup.find('h1', class_='QuestionHeader-title')
        if not title_element:
            title_element = soup.find('h1', class_='Post-Title')
        if title_element:
            title = title_element.get_text(strip=True)
        
        # 提取正文
        content_div = soup.find('div', class_='Post-RichTextContainer')
        if not content_div:
            content_div = soup.find('div', class_='QuestionAnswer-content')
        if not content_div:
            content_div = soup.find('div', class_='RichContent')
        
        content_text = ""
        if content_div:
            # 使用html2text将HTML转换为Markdown格式文本
            h = html2text.HTML2Text()
            h.ignore_links = True  # 忽略链接
            h.ignore_images = True  # 忽略图片
            h.ignore_emphasis = True  # 忽略斜体/粗体格式
            content_text = h.handle(str(content_div))
        
        return title, content_text
    
    def process_full_content(driver, item, output_file, index):
        """处理单个收藏项并提取完整内容"""
        # 提取文章标题和链接
        title, link = extract_title_and_link(item)
        if not title or not link:
            print(f"无法提取第 {index} 项的标题和链接")
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"{index}. 无法提取标题和链接\n")
                f.write("-" * 80 + "\n")
            return
        
        print(f"处理 ({index}): {title}")
        
        # 在新标签页中打开文章
        driver.execute_script(f"window.open('{link}');")
        driver.switch_to.window(driver.window_handles[1])
        
        try:
            # 等待文章加载
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".Post-Main, .Question-main"))
            )
            
            # 获取完整的HTML源码
            html_content = driver.page_source
            
            # 提取纯文本内容
            article_title, article_content = extract_text_content(html_content)
            
            # 如果提取失败，使用原标题
            if not article_title:
                article_title = title
            
            # 写入输出文件
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"{index}. {article_title}\n")
                f.write(f"链接: {link}\n")
                f.write("-" * 80 + "\n")
                f.write(article_content.strip() + "\n")
                f.write("\n" + "=" * 80 + "\n\n")
            
            print(f"✅ 已保存: {article_title}")
            
        except Exception as e:
            print(f"处理文章失败: {str(e)}")
            # 如果提取失败，至少保存标题和链接
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"{index}. {title}\n")
                f.write(f"链接: {link}\n")
                f.write(f"错误: 无法提取内容 ({str(e)})\n")
                f.write("\n" + "=" * 80 + "\n\n")
        finally:
            # 关闭文章标签页，切回主窗口
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(random.uniform(1, 2))  # 随机等待时间，避免请求过快
    
    # 主执行逻辑
    print("="*50)
    print("知乎收藏夹下载工具")
    print(f"收藏夹ID: {collection_id}")
    print(f"抓取模式: {'仅标题和链接' if only_title_link else '完整内容'}")
    print(f"页码范围: {page_range_desc}")
    print(f"输出文件: {OUTPUT_FILE}")
    print("="*50)
    
    # 初始化输出文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(f"知乎收藏内容汇总\n")
        f.write(f"收藏夹ID: {collection_id}\n")
        f.write(f"抓取模式: {'仅标题和链接' if only_title_link else '完整内容'}\n")
        f.write(f"页码范围: {page_range_desc}\n")
        f.write(f"生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
    
    # 初始化浏览器
    driver = init_driver()
    total_items = 0  # 总项目计数
    
    try:
        # 登录
        if not login(driver):
            print("登录失败，无法继续下载")
            return
        
        # 确定起始页码和结束页码
        start_page = from_page
        end_page = to_page
        
        # 遍历指定范围内的所有页面
        for current_page in range(start_page, end_page + 1):
            print(f"\n===== 开始处理第 {current_page} 页 =====")
            
            try:
                # 获取当前页收藏项
                items = get_page_items(driver, current_page)
                
                # 处理当前页所有收藏项
                for i, item in enumerate(items, 1):
                    index = total_items + i
                    
                    if only_title_link:
                        # 仅保存标题和链接
                        title, link = extract_title_and_link(item)
                        if title and link:
                            print(f"处理 ({index}): {title}")
                            save_title_and_link(OUTPUT_FILE, index, title, link)
                        else:
                            print(f"无法提取第 {index} 项的标题和链接")
                            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                                f.write(f"{index}. 无法提取标题和链接\n")
                                f.write("-" * 80 + "\n")
                    else:
                        # 抓取完整内容
                        process_full_content(driver, item, OUTPUT_FILE, index)
                
                total_items += len(items)
                print(f"===== 第 {current_page} 页处理完成，共 {len(items)} 项 =====")
                
                # 如果不是最后一页，等待一下再处理下一页
                if current_page < end_page:
                    time.sleep(random.uniform(2, 4))
                    
            except Exception as e:
                print(f"处理第 {current_page} 页时出错: {str(e)}")
                # 尝试下一页
                if current_page < end_page:
                    time.sleep(5)  # 出错后等待更长时间
    
    except Exception as e:
        print(f"主流程出错: {str(e)}")
        driver.save_screenshot("main_error.png")
    finally:
        print("关闭浏览器...")
        driver.quit()
        print(f"\n🎉 下载完成！所有内容保存在: {os.path.abspath(OUTPUT_FILE)}")
        print(f"总共处理了 {total_items} 个收藏项")

# 使用示例
if __name__ == "__main__":
    # 示例1：抓取完整内容，第65页
    process_zhihu("88652213", only_title_link=False, from_page=1, to_page=10)
    
    # 示例2：只抓取标题和链接，第65页
    # process_zhihu("713314943", only_title_link=True, from_page=65, to_page=65)
    
    # 示例3：抓取完整内容，第65页到第70页
    # process_zhihu("713314943", only_title_link=False, from_page=65, to_page=70)
    
    # 示例4：只抓取标题和链接，第65页到第70页
    # process_zhihu("713314943", only_title_link=True, from_page=65, to_page=70)
