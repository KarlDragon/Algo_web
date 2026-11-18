"""Idempotent demo data + optional explicit admin bootstrap.
Run from BE: py -m seed (after Alembic upgrade).
Never ships a hardcoded password.
"""
import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import select
from database import SessionLocal
from Models.Users import User
from Models.Algorithms import Category, Algorithm, HomeBanner
from Schemas.ContentSchemas import AlgorithmInput,CodeSampleInput,CategoryInput,ExampleInput,DiagramInput,VisualizationInput
from Services.AlgorithmService import AlgorithmService
from Services.Register import RegisterService
from Services.ContentHelpers import slugify

load_dotenv(Path(__file__).resolve().parent/'.env')
log=logging.getLogger(__name__)

SEED_ALGOS=[
 ('bubble-sort','Bubble Sort','Sắp xếp nổi bọt','Duyệt từng cặp phần tử kề nhau và đổi chỗ nếu sai thứ tự.','EASY','O(n)','O(n²)','O(n²)','O(1)',
 '''for i from 0 to n-2:
    swapped = false
    for j from 0 to n-i-2:
        if a[j] > a[j+1]: swap(a[j],a[j+1]); swapped=true
    if not swapped: break''',
 '''def bubble_sort(a):
    a = a[:]
    for i in range(len(a)):
        swapped = False
        for j in range(len(a)-1-i):
            if a[j] > a[j+1]:
                a[j], a[j+1] = a[j+1], a[j]
                swapped = True
        if not swapped: break
    return a''', 'sorting'),
 ('selection-sort','Selection Sort','Sắp xếp chọn','Mỗi lượt chọn phần tử nhỏ nhất trong phần chưa sắp xếp và đưa lên đầu.','EASY','O(n²)','O(n²)','O(n²)','O(1)',
 '''for i in 0..n-1:
    min = i
    for j in i+1..n-1: if a[j] < a[min]: min = j
    swap(a[i],a[min])''',
 '''def selection_sort(a):
    a = a[:]
    for i in range(len(a)):
        m = min(range(i, len(a)), key=a.__getitem__)
        a[i], a[m] = a[m], a[i]
    return a''','sorting'),
 ('insertion-sort','Insertion Sort','Sắp xếp chèn','Đưa phần tử hiện tại vào đúng vị trí trong dãy đã được sắp xếp bên trái.','EASY','O(n)','O(n²)','O(n²)','O(1)',
 '''for i in 1..n-1:
    key = a[i]; j=i-1
    while j>=0 and a[j]>key: a[j+1]=a[j]; j--
    a[j+1]=key''',
 '''def insertion_sort(a):
    a = a[:]
    for i in range(1, len(a)):
        v, j = a[i], i-1
        while j >= 0 and a[j] > v:
            a[j+1] = a[j]; j -= 1
        a[j+1] = v
    return a''','sorting'),
 ('merge-sort','Merge Sort','Sắp xếp trộn','Chia mảng thành hai nửa, sắp xếp đệ quy rồi trộn hai dãy đã sắp.','MEDIUM','O(n log n)','O(n log n)','O(n log n)','O(n)',
 '''merge_sort(a):
    if len(a)<=1: return a
    split a into left,right
    return merge(merge_sort(left),merge_sort(right))''',
 '''def merge_sort(a):
    if len(a) <= 1: return a[:]
    m = len(a)//2
    l, r = merge_sort(a[:m]), merge_sort(a[m:])
    out=[]; i=j=0
    while i<len(l) and j<len(r):
        if l[i]<=r[j]:out.append(l[i]);i+=1
        else:out.append(r[j]);j+=1
    return out+l[i:]+r[j:]''','sorting'),
 ('quick-sort','Quick Sort','Sắp xếp nhanh','Chọn pivot, phân vùng mảng theo pivot rồi sắp xếp các phần đệ quy.','MEDIUM','O(n log n)','O(n log n)','O(n²)','O(n)',
 '''quick_sort(a):
    if len(a)<=1: return a
    pivot=a[len(a)//2]
    return quick_sort(<pivot) + equal(pivot) + quick_sort(>pivot)''',
 '''def quick_sort(a):
    if len(a)<=1: return a[:]
    p=a[len(a)//2]
    return quick_sort([x for x in a if x<p])+[x for x in a if x==p]+quick_sort([x for x in a if x>p])''','sorting'),
 ('binary-search','Binary Search','Tìm kiếm nhị phân','Tìm trên mảng đã sắp xếp bằng cách liên tục giảm một nửa khoảng tìm kiếm.','EASY','O(1)','O(log n)','O(log n)','O(1)',
 '''lo=0; hi=n-1
while lo<=hi:
    mid=(lo+hi)//2
    if a[mid]==target: return mid
    if a[mid]<target: lo=mid+1
    else: hi=mid-1
return -1''',
 '''def binary_search(a, target):
    lo, hi=0,len(a)-1
    while lo<=hi:
        m=(lo+hi)//2
        if a[m]==target:return m
        if a[m]<target:lo=m+1
        else:hi=m-1
    return -1''','searching'),
 ('bfs','Breadth-First Search (BFS)','Duyệt đồ thị theo chiều rộng','Dùng hàng đợi để duyệt tất cả đỉnh cách nguồn một cạnh trước khi đi xa hơn.','MEDIUM','O(V+E)','O(V+E)','O(V+E)','O(V)',
 '''queue=[start]; visited={start}
while queue:
    u=dequeue()
    for v in neighbors(u):
        if v not in visited: visited.add(v); enqueue(v)''',
 '''from collections import deque
def bfs(graph, start):
    q=deque([start]); visited={start}; order=[]
    while q:
        u=q.popleft(); order.append(u)
        for v in graph.get(u, []):
            if v not in visited:
                visited.add(v);q.append(v)
    return order''','graph'),
 ('dfs','Depth-First Search (DFS)','Duyệt đồ thị theo chiều sâu','Đi theo từng nhánh sâu nhất trước khi quay lui khám phá nhánh khác.','MEDIUM','O(V+E)','O(V+E)','O(V+E)','O(V)',
 '''dfs(u):
    mark u visited
    for v in neighbors(u):
        if v not visited: dfs(v)''',
 '''def dfs(graph, start):
    visited=set(); order=[]
    def visit(u):
        if u in visited:return
        visited.add(u);order.append(u)
        for v in graph.get(u, []):visit(v)
    visit(start)
    return order''','graph'),
 ('dijkstra','Dijkstra','Tìm đường đi ngắn nhất','Tìm đường đi ngắn nhất từ đỉnh nguồn khi trọng số cạnh không âm bằng hàng đợi ưu tiên.','HARD','O((V+E) log V)','O((V+E) log V)','O((V+E) log V)','O(V+E)',
 '''dist[source]=0; heap=[(0,source)]
while heap:
    (d,u)=pop_min()
    if d!=dist[u]: continue
    for (v,w) in adj[u]:
        if dist[v]>d+w: dist[v]=d+w; push(dist[v],v)''',
 '''import heapq
def dijkstra(g,s):
    d={v:float('inf') for v in g};d[s]=0
    pq=[(0,s)]
    while pq:
        cost,u=heapq.heappop(pq)
        if cost!=d[u]:continue
        for v,w in g.get(u,[]):
            if cost+w<d.get(v,float('inf')):
                d[v]=cost+w;heapq.heappush(pq,(d[v],v))
    return d''','graph'),
]


def seed():
    with SessionLocal() as db:
        svc=AlgorithmService(db)
        for name,slug in [('Sắp xếp','sorting'),('Tìm kiếm','searching'),('Đồ thị','graph'),('Quy hoạch động','dynamic-programming')]:
            if not db.scalar(select(Category).where(Category.slug==slug)):
                svc.create_category(CategoryInput(name=name,slug=slug,description='Kiến thức '+name.lower()+' bằng tiếng Việt'))
        categories={c.slug:c.id for c in db.scalars(select(Category))}
        created=0
        for slug,name,short,summary,level,best,avg,worst,space,pseudo,code,cat in SEED_ALGOS:
            if db.scalar(select(Algorithm).where(Algorithm.slug==slug)):
                continue
            svc.save_algorithm(AlgorithmInput(
                slug=slug,name=name,summary=summary,difficulty=level,category_id=categories[cat],
                theory=f'{short}. {summary} Hãy quan sát mô phỏng để theo dõi các bước thực hiện.',
                pseudocode=pseudo,code_samples=[CodeSampleInput(language='python',code=code)],
                complexity={'time_best':best,'time_average':avg,'time_worst':worst,'space':space},
                tags=[short,cat],has_simulation=True,
                examples=[ExampleInput(title='Ví dụ minh họa',input_data='[5, 1, 4, 2, 8]',
                                       expected_output='Tùy thuộc thuật toán',explanation=summary,sort_order=1)],
                diagrams=[DiagramInput(title='Sơ đồ tổng quan',diagram_type='mermaid',
                                       source_text='flowchart TD\n  A[Bắt đầu] --> B[Thực hiện thuật toán]\n  B --> C[Kết thúc]',sort_order=1)],
                visualization_config=VisualizationInput(renderer_key=slug,config_json=json.dumps({'speed':1,'showSteps':True}))))
            created+=1
        if not db.scalar(select(HomeBanner.id)):
            db.add(HomeBanner(title='Khám phá thuật toán',image_url='/assets/algoweb-banner.svg',
                              link_url='/algorithms/bubble-sort',sort_order=1,is_active=True))
            db.commit()
        username=os.getenv('SEED_ADMIN_USERNAME','').strip()
        email=os.getenv('SEED_ADMIN_EMAIL','').strip().lower()
        password=os.getenv('SEED_ADMIN_PASSWORD','')
        if username or email or password:
            if not all((username,email,password)):
                raise ValueError('Phải có đủ 3 biến SEED_ADMIN_USERNAME, SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD')
            checker=RegisterService(db)
            checker.check_username(username)
            checker.check_email(email)
            checker.check_password(password)
            existing=db.scalar(select(User).where((User.username==username)|(User.email==email)))
            if existing is None:
                db.add(User(username=username,email=email,hashPassword=checker.hash_password(password),role='ADMIN'))
                db.commit()
                print('Đã tạo ADMIN từ biến môi trường (không in mật khẩu).')
            elif existing.role!='ADMIN' or existing.username!=username or existing.email!=email:
                raise ValueError('Tên đăng nhập/email trùng người dùng khác; không tự nâng quyền')
            else:print('ADMIN đã tồn tại; không thay đổi mật khẩu.')
        print(f'Hoàn tất seed: {created} thuật toán mới. Không xóa dữ liệu cũ.')

if __name__=='__main__':seed()
