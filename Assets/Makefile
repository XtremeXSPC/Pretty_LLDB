PLANTUML ?= plantuml
PLANTUML_FLAGS ?= -tsvg

SOURCE_DIR := PlantUML
OUTPUT_DIR := Generated
SOURCES := $(wildcard $(SOURCE_DIR)/*.puml)
SVGS := $(patsubst $(SOURCE_DIR)/%.puml,$(OUTPUT_DIR)/%.svg,$(SOURCES))

.PHONY: all svg clean check list

all: svg

svg: $(SVGS)

$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

$(OUTPUT_DIR)/%.svg: $(SOURCE_DIR)/%.puml | $(OUTPUT_DIR)
	$(PLANTUML) $(PLANTUML_FLAGS) -output "$(OUTPUT_DIR)" "$<"

check:
	$(PLANTUML) -checkonly $(SOURCES)

list:
	@printf '%s\n' $(SOURCES)

clean:
	rm -f $(OUTPUT_DIR)/*.svg
