package com.salonexplorer.config;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.salonexplorer.model.Salon;
import com.salonexplorer.repository.SalonRepository;
import com.salonexplorer.seed.SalonSeedRecord;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.io.IOException;
import java.io.InputStream;
import java.util.List;

@Component
public class DataSeeder implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(DataSeeder.class);
    private static final String SEED_FILE = "data/salons_clean.json";

    private final SalonRepository salonRepository;
    private final ObjectMapper objectMapper = new ObjectMapper();

    public DataSeeder(SalonRepository salonRepository) {
        this.salonRepository = salonRepository;
    }

    @Override
    @Transactional
    public void run(ApplicationArguments args) {
        if (salonRepository.count() > 0) {
            log.debug("Salons table already contains data, skipping seed import");
            return;
        }

        ClassPathResource resource = new ClassPathResource(SEED_FILE);
        if (!resource.exists()) {
            log.warn("Seed file not found at classpath:{} — skipping import", SEED_FILE);
            return;
        }

        try (InputStream inputStream = resource.getInputStream()) {
            List<SalonSeedRecord> records = objectMapper.readValue(
                    inputStream,
                    new TypeReference<List<SalonSeedRecord>>() {
                    }
            );

            if (records == null || records.isEmpty()) {
                log.info("Seed file is empty, no salons imported");
                return;
            }

            List<Salon> salons = records.stream().map(this::toSalon).toList();
            salonRepository.saveAll(salons);
            log.info("Imported {} salon(s) from {}", salons.size(), SEED_FILE);
        } catch (IOException exception) {
            log.error("Failed to read seed file {}: {}", SEED_FILE, exception.getMessage());
        }
    }

    private Salon toSalon(SalonSeedRecord record) {
        Salon salon = new Salon();
        salon.setName(record.getName());
        salon.setAddress(record.getAddress());
        salon.setDistrict(record.getDistrict());
        salon.setPhone(record.getPhone());
        salon.setWebsiteUrl(record.getWebsiteUrl());
        salon.setServices(record.getServices());
        salon.setPriceRange(record.getPriceRange());
        salon.setRating(record.getRating());
        salon.setReviewCount(record.getReviewCount());
        salon.setSource(record.getSource());
        salon.setExternalId(record.getExternalId());
        return salon;
    }
}
