import pip._vendor.requests as requests
import sys
import os
import config
import logging
import constants
import helper_functions
import mappers

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def process_libraries_data(libraries_data):
    # Extract and return custom libraries from API response.
    return [
        {
            "id": item["id"],
            "name": item["name"],
            "referenceId": item.get("referenceId"),
            "filePath": None,
        }
        for item in libraries_data.get("_embedded", {}).get("items", [])
        if item.get("type", "").lower() == "custom"
    ]


def export_libraries_to_xml(libraries_info, domain, headers):
    # Export libraries to XML, save files locally.
    if not os.path.exists("exports"):
        os.makedirs("exports")

    for library in libraries_info:
        if (library["referenceId"] in libraries_not_to_post) is False:
            logging.info(f"Exporting {library['name']}...")
            export_url = (
                f'{domain}{constants.ENDPOINT_LIBRARIES}/{library["id"]}/export'
            )
            response = requests.get(export_url, headers=headers)
            if response.status_code == 200:
                file_path = os.path.join("exports", f"{library['id']}.xml")
                with open(file_path, "wb") as file:
                    file.write(response.content)
                library["filePath"] = file_path
                logging.info(f"Exported {library['id']}.")
            else:
                logging.error(
                    f"Export failed for {library['id']}. Status: {response.status_code}. Text: {response.json()}"
                )


def import_libraries(libraries_info, url, headers):
    # Import libraries from local XML files to the target system.
    for library in libraries_info:
        if library.get("filePath") and os.path.exists(library["filePath"]):
            with open(library["filePath"], "rb") as file:
                files = {
                    "file": (
                        os.path.basename(library["filePath"]),
                        file,
                        "application/xml",
                    )
                }
                data = {"referenceId": library["referenceId"], "name": library["name"]}
                # Ensure headers do not automatically set a conflicting content-type for multipart/form-data
                local_headers = headers.copy()
                local_headers.pop(
                    "Content-Type", None
                )  # Remove content-type if set, as it will be set by requests
                logging.info(f"Importing {library['name']}...")
                response = requests.post(
                    url, headers=local_headers, data=data, files=files
                )
                if response.status_code == 200:
                    logging.info(f"Imported {library['name']}.")
                else:
                    logging.error(
                        f"Import failed for {library['name']}. Status: {response.status_code}. Response: {response.json()}"
                    )


def main(start_domain, post_domain, start_head, post_head):
    logging.info("tentant_config_migration_libraries | START")

    sys.stdout.reconfigure(encoding="utf-8")
    source_libraries_data = helper_functions.get_request(
        start_domain,
        constants.ENDPOINT_LIBRARIES + "?size=10000",
        start_head,
    )
    dest_libraries_data = helper_functions.get_request(
        post_domain,
        constants.ENDPOINT_LIBRARIES + "?size=10000",
        post_head,
    )

    source_libraries_mapped = mappers.map_libraries(source_libraries_data)
    dest_libraries_mapped = mappers.map_libraries(dest_libraries_data)

    matches = helper_functions.find_matches(
        source_libraries_mapped, dest_libraries_mapped, "referenceId"
    )

    libraries_not_to_post = []

    for item in source_libraries_mapped:
        if item.get("type", "").lower() == "custom":
            if item["referenceId"] in matches:
                libraries_not_to_post.append(item["referenceId"])
                if (
                    helper_functions.is_ir_object_same(item, dest_libraries_mapped)
                    is False
                ):
                    uuid = matches[item["referenceId"]]
                    del item["referenceId"]
                    helper_functions.put_request(
                        uuid,
                        item,
                        post_domain + constants.ENDPOINT_LIBRARIES,
                        post_head,
                    )
                else:
                    logging.info(f"Library [{item['name']}] is the same.")

    logging.info("Exporting libraries for POSTING...")
    libraries_info = process_libraries_data(source_libraries_data)
    export_libraries_to_xml(libraries_info, start_domain, start_head)
    import_libraries(
        libraries_info,
        f"{post_domain}{constants.ENDPOINT_LIBRARIES}/import",
        post_head,
    )
    logging.info("tentant_config_migration_libraries | END")

if __name__ == "__main__":
    logging.info("tenant_config_migration_libraries | START")
    main(config.source_domain, config.dest_domain, config.source_head, config.dest_head)
    logging.info("tenant_config_migration_libraries | END")
