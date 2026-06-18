import fitz
import os
import re
import shutil

pdf_path = r'c:\Users\johna\liturgio\propers-parser\GM\gregorian-missal.pdf'
output_dir = r'c:\Users\johna\liturgio\propers-parser\GM\sections'

# Clear and recreate output dir
if os.path.exists(output_dir):
    shutil.rmtree(output_dir)
os.makedirs(output_dir)

doc = fitz.open(pdf_path)
toc = doc.get_toc()
total_pages = doc.page_count

parent_sections = ['The Liturgical Year', 'Feasts of the Lord and Solemnities of Saints']

# Find parent section boundaries
parent_info = {}
for i, (level, title, page) in enumerate(toc):
    if level == 1 and title in parent_sections:
        end_page = total_pages
        for j in range(i + 1, len(toc)):
            if toc[j][0] == 1:
                end_page = toc[j][2] - 1
                break
        parent_info[title] = (page, end_page)

def sanitize(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name.strip()

total_saved = 0

for parent_name in parent_sections:
    if parent_name not in parent_info:
        continue
    parent_start, parent_end = parent_info[parent_name]

    subsections = []
    in_this_parent = False
    for i, (level, title, page) in enumerate(toc):
        if level == 1 and title == parent_name:
            in_this_parent = True
            continue
        if level == 1 and in_this_parent:
            break
        if in_this_parent and level == 2:
            subsections.append((title, page))

    folder = os.path.join(output_dir, sanitize(parent_name))
    os.makedirs(folder)

    pad = len(str(len(subsections)))

    for i, (title, start_page) in enumerate(subsections):
        end_page = subsections[i + 1][1] - 1 if i + 1 < len(subsections) else parent_end
        end_page = max(end_page, start_page)

        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_page - 1, to_page=end_page - 1)
        new_doc.set_page_labels([{"startpage": 0, "style": "D", "firstpagenum": start_page}])

        number = str(i + 1).zfill(pad)
        filename = f"{number} {sanitize(title)}.pdf"
        new_doc.save(os.path.join(folder, filename))
        new_doc.close()
        print(f"  {filename} (pages {start_page}-{end_page})")
        total_saved += 1

doc.close()
print(f"\nDone! {total_saved} files written to {output_dir}")
